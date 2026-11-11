from langchain_openai import ChatOpenAI
from langgraph.graph import START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition
from sqlalchemy.orm import Session
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

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

预约成功后状态是待审核，必须管理员确认实验室（或设备）后才能使用。
不要瞎编数据库里不存在的实验室或者设备信息。
如果是问开放时间或者实验室规则，优先调用search_lab_docs, 不要凭空回答。
"""


def build_agent(db: Session, current_user: User):
    tools = agent_tools.build_tools(db, current_user)
    llm = ChatOpenAI(
        api_key=settings.LLM_API_KEY,
        base_url=settings.LLM_BASE_URL,
        model=settings.LLM_MODEL,
        temperature=0,
        extra_body={"thinking": {"type": "disabled"}},
    ).bind_tools(tools)

    def agent_node(state: MessagesState):
        """langgraph 执行的工作流的节点"""
        response = llm.invoke(state["messages"])
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


def run_agent(db: Session, current_user: User, data: ChatRequest):
    """大模型对话"""
    if not data.messages:
        raise BusinessException(message="对话内容为空")
    history = []
    for message in data.messages:
        if message.role == "user" and message.content.strip():
            history.append(HumanMessage(content=message.content.strip()))
        elif message.role == "assistant" and message.content.strip():
            history.append(AIMessage(content=message.content.strip()))
    if not history:
        raise BusinessException(message="请输入您要对话的内容")

    agent = build_agent(db, current_user)
    try:
        result = agent.invoke(
            {"messages": [SystemMessage(content=SYSTEM_PROMPT), *history]},
            config={"recursion_limit": 10},  # 设置对话上限是10轮
        )
    except Exception:
        raise BusinessException(message="大模型调用失败，请稍后重试")

    messages = result.get("messages") or []
    if not messages:
        raise BusinessException(message="大模型没有返回任何内容")
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and msg.content:
            content = msg.content
            if isinstance(content, list):
                content = "".join(
                    part.get("text", "") if isinstance(part, dict) else str(part)
                    for part in content
                )
            if str(content).strip():
                return str(content).strip()
