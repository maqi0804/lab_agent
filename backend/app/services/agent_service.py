import traceback
from typing import Any

from langchain_openai import ChatOpenAI
from langgraph.graph import START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition
from numpy import isin
from sqlalchemy.orm import Session
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, ToolMessage

from app.common.exceptions import BusinessException
from app.config import settings
from app.models.user import User
from app.schemas.ai import ChatRequest
from app.services import agent_tools

SYSTEM_PROMPT = """你是智能实验室预约系统的Agent，回答要简洁。
你可以：
1.使用search_lab_docs 工具，查询实验室的规则、安全、开放时间等问题。
2.使用list_open_labs/list_lab_equipments 工具，查询真实的实验室、设备。
3.在用户进行了预约的确认后，使用create_lab_reservation 工具，来进行真实的预约落库。
4.使用get_today 来进行日期的换算。


## 必须遵守
当用户提到了 今天、明天、后天 等日期相关的问题，请先调用 get_today 来获取日期，**不要直接返回 我需要确定明天的具体日期**。

在用户提交预约之前必须向用户复述：实验室的ID与名称，或设备ID与名称，日期，开始时间，结束时间，并得到用户确认后再进行实际操作。
用户没说[确认][确认预约][就这样预约]等确定性回复前，不要调用 create_lab_reservation。
工作流的确认环节里如果缺少了 lab_id,请先list_open_labs 来获取,查到了lab_id再创建，不要瞎写。
工作流的确认环节缺少了eqipment_id,请先list_lab_equipments 来获取,查到了equipment_id再创建，不要瞎写。
使用 list_my_reservations 查询自己的预约列表，拿到预约ID后，再调用 cancel_lab_reservation 取消预约；取消前需要向用户复述预约信息并确认。

预约成功后状态是待审核，必须管理员确认实验室（或设备）后才能使用。
不要瞎编数据库里不存在的实验室或者设备信息。
如果是问开放时间或者实验室规则，优先调用search_lab_docs, 不要凭空回答。
"""

TOOL_LABELS = {
    "search_lab_docs": "检索实验室的知识库",
    "list_open_labs": "查询开放实验室",
    "list_lab_equipments": "查询实验室的设备",
    "create_lab_reservation": "创建实验室预约",
    "get_today": "获取今天的日期",
    "list_my_reservations": "查询我的预约",
    "cancel_lab_reservation": "取消实验室预约",
}


def _build_history(data: ChatRequest) -> list:
    """前端的消息 转成 LangChain 的消息对象"""
    history = []
    for message in data.messages:
        if message.role == "user" and message.content.strip():
            history.append(HumanMessage(content=message.content.strip()))
        elif message.role == "assistant" and message.content.strip():
            history.append(AIMessage(content=message.content.strip()))
    if not history:
        raise BusinessException(message="请输入您的对话内容")
    return history


def _tool_output_preview(output: Any, limit: int = 200):
    """把工具输出的结果收成短文本预览，避免整段json污染输出的区域"""
    if isinstance(output, ToolMessage):
        output = output.content
    text = (
        output if isinstance(output, str) else str(output)
    )  # output有可能是dict -> str
    return text if len(text) <= limit else text[:limit] + "..."


def _chunk_text(chunk: Any):
    """
    从模型的流式输出里面拿到纯文本
    chunk.content  可能是str [{type, text}, ....]等类型  统一处理成字符串
    """
    if chunk is None:
        return ""
    # chunk 如果是AIMessage 类型的 则可以取出 content
    content = getattr(chunk, "content", None)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
            if isinstance(part, dict):
                parts.append(part.get("text") or "")
        return "".join(parts)
    return str(content) if content is not None else ""


async def stream_agent(db: Session, current_user: User, data: ChatRequest):
    """
    生成器：边跑agent边进行yield事件，提供SSE输出给前端

    事件类型：status / tool_start / tool_end / token / done / error

    """
    try:
        history = _build_history(data)
        agent = build_agent(db, current_user)
        inputs = {"messages": [SystemMessage(content=SYSTEM_PROMPT), *history]}

        yield {"type": "status", "message": "正在思考..."}

        async for event in agent.astream_events(
            inputs, version="v2", config={"recursion_limit": 10}
        ):
            print("event:", event.get("event"), event.get("name"))
            kind = event.get("event")
            if kind == "on_tool_start":
                name = event.get("name") or ""  # tool的名称
                yield {
                    "type": "tool_start",
                    "name": name,
                    "label": TOOL_LABELS.get(name, name),
                }
            elif kind == "on_tool_end":
                name = event.get("name") or ""  # tool的名称
                yield {
                    "type": "tool_end",
                    "name": name,
                    "label": TOOL_LABELS.get(name, name),
                    "preview": _tool_output_preview(
                        (event.get("data") or {}).get("output")
                    ),
                }
            elif kind == "on_chat_model_stream":
                metadata = event.get("metadata") or {}
                if metadata.get("langgraph_node") not in (None, "agent"):
                    continue
                text = _chunk_text((event.get("data") or {}).get("chunk"))
                yield {"type": "token", "content": text}
        yield {"type": "done"}

    except BusinessException as e:
        yield {"type": "error", "message": e.message}
    except Exception as e:
        # traceback.print_exc()
        yield {"type": "error", "message": "大模型调用失败，请稍后重试"}


def build_agent(db: Session, current_user: User):
    tools = agent_tools.build_tools(db, current_user)
    llm = ChatOpenAI(
        api_key=settings.LLM_API_KEY,
        base_url=settings.LLM_BASE_URL,
        model=settings.LLM_MODEL,
        temperature=0,
        streaming=True,  # 开启流式输出  stream_event 接收到逐字返回的token
        extra_body={"thinking": {"type": "disabled"}},
    ).bind_tools(tools)

    async def agent_node(state: MessagesState):
        """langgraph 执行的工作流的节点"""
        response = await llm.ainvoke(state["messages"])
        return {"messages": [response]}

    graph = StateGraph(MessagesState)
    graph.add_node("agent", agent_node)  # 调用大模型的节点
    graph.add_node("tools", ToolNode(tools))  # tool call的节点
    graph.add_edge(START, "agent")  # 流程的起点，call LLM
    graph.add_conditional_edges(
        "agent", tools_condition
    )  # 看有无 tool_call  有就继续call  没有就END 输出
    graph.add_edge("tools", "agent")  # 让agent看tool调用的结果
    return graph.compile()


# def run_agent(db: Session, current_user: User, data: ChatRequest):
#     """大模型对话"""
#     if not data.messages:
#         raise BusinessException(message="对话内容为空")
#     history = []
#     for message in data.messages:
#         if message.role == "user" and message.content.strip():
#             history.append(HumanMessage(content=message.content.strip()))
#         elif message.role == "assistant" and message.content.strip():
#             history.append(AIMessage(content=message.content.strip()))
#     if not history:
#         raise BusinessException(message="请输入您要对话的内容")

#     agent = build_agent(db, current_user)
#     try:
#         result = agent.invoke(
#             {"messages": [SystemMessage(content=SYSTEM_PROMPT), *history]},
#             config={"recursion_limit": 10},  # 设置对话上限是10轮
#         )
#     except Exception:
#         raise BusinessException(message="大模型调用失败，请稍后重试")

#     messages = result.get("messages") or []
#     if not messages:
#         raise BusinessException(message="大模型没有返回任何内容")
#     for msg in reversed(messages):
#         if isinstance(msg, AIMessage) and msg.content:
#             content = msg.content
#             if isinstance(content, list):
#                 content = "".join(
#                     part.get("text", "") if isinstance(part, dict) else str(part)
#                     for part in content
#                 )
#             if str(content).strip():
#                 return str(content).strip()
