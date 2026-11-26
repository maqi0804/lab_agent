# 智能实验室预约系统 · Lab Reservation Agent

> 一个把「实验室预约」这条业务流交给大模型 Agent 跑通的全栈项目：用户用自然语言说一句"帮我预约后天下午的光学实验台"，Agent 自己查实验室、查设备、核对日期、复述确认、落库提交，全程流式返回，每一步工具调用都可见。

<p>
  <img alt="Python" src="https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white">
  <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white">
  <img alt="Vue" src="https://img.shields.io/badge/Vue-3.5-4FC08D?logo=vue.js&logoColor=white">
  <img alt="Element Plus" src="https://img.shields.io/badge/Element%20Plus-2.14-409EFF">
  <img alt="MySQL" src="https://img.shields.io/badge/MySQL-8.0-4479A1?logo=mysql&logoColor=white">
  <img alt="LangGraph" src="https://img.shields.io/badge/LangGraph-1.x-1C3C3C">
  <img alt="ChromaDB" src="https://img.shields.io/badge/ChromaDB-1.5-FF6B6B">
</p>

---

## 目录

- [项目背景与目标](#项目背景与目标)
- [界面预览](#界面预览)
- [功能清单](#功能清单)
- [系统架构](#系统架构)
- [核心流程](#核心流程)
- [AI Agent 设计](#ai-agent-设计)
- [技术栈](#技术栈)
- [数据模型](#数据模型)
- [目录结构](#目录结构)
- [快速开始](#快速开始)
- [接口一览](#接口一览)
- [实现成果](#实现成果)

---

## 项目背景与目标

高校和企业的实验室预约，长期靠「Excel 排期 + 微信群喊话 + 管理员人工核对」：谁占了这个时段、设备是不是在维修、开放时间对不对、约了设备还能不能约整间实验室——这些规则散落在纸质规范和口头约定里，用户不清楚，管理员每单都要人工拦一遍。

这个项目的目标不是再做一个表单系统，而是验证一件事：

**把散落的规则变成机器可执行的约束，把繁琐的多步操作交给 Agent 完成。**

具体拆成三层目标：

| 层次 | 目标 | 落地方式 |
| --- | --- | --- |
| 业务层 | 实验室/设备的浏览、预约、审核、取消全流程可用 | FastAPI + MySQL，预约状态机 + 冲突检测 |
| 知识层 | 开放时间、安全规范等"规则类问题"能被准确回答，而不是靠模型编 | ChromaDB 向量库 + 中文句向量检索 |
| 交互层 | 用户不必学会点哪几个按钮，说一句话就能完成预约 | LangGraph Agent + 7 个业务工具 + SSE 流式输出 |

一句话概括设计意图：**大模型负责理解和编排，业务规则仍然由后端代码强制执行。**
Agent 不拥有任何特权，它调用的是和前端按钮完全相同的服务层方法，因此"模型幻觉"最多导致一次失败的函数调用，不会造成脏数据。

---

## 界面预览

### 1. 登录

支持账号密码登录，JWT 无状态鉴权，前端路由守卫拦截未登录访问。

![登录页](docs/images/01-login.png)

### 2. 首页工作台

聚合当前用户的身份、开放实验室数量、与我相关的预约数量，以及三个快捷入口（AI 助手 / 实验室列表 / 我的预约）。

![首页](docs/images/02-home.png)

### 3. 实验室列表

卡片式展示实验室名称、位置、容量、开放时段，支持关键字查询；每个实验室提供「查看设备」和「预约」两个动作。

![实验室列表](docs/images/03-lab-list.jpg)

### 4. AI 助手 · 知识库问答

问"进入实验室要注意什么"，Agent 调用 `search_lab_docs` 检索向量库，回答里带出安全规范原文，而不是自由发挥。消息上方灰色的 `· 开始 / · 完成 / · 输出结果` 就是实时推送的工具调用轨迹。

![知识库问答](docs/images/04-ai-knowledge-qa.png)

### 5. AI 助手 · 工具调用与参数推理

问"帮我查询有机化学实验室可以预约的设备有哪些"，Agent 先 `list_open_labs` 拿到 `lab_id=3`，再 `list_lab_equipments` 查设备，最后把设备 ID、名称、规格、数量整理成表。注意它顺手纠正了用户的口误（"有机化学"→「化学实验室-有机」）。

![工具调用](docs/images/05-ai-tool-call.png)

### 6. AI 助手 · 预约确认与取消确认

"帮我预约后天下午的光学实验台"——Agent 先调 `get_today` 换算"后天"=2026-11-28，再把实验室 ID / 设备 ID / 日期 / 时段复述一遍等用户确认；确认后才调 `create_lab_reservation` 落库，返回状态「待审核」。取消同理，先 `list_my_reservations` 拿到预约 ID 再确认。

![预约确认](docs/images/06-ai-confirm-cancel.png)

### 7. 我的预约

按状态筛选的预约台账，区分「实验室 / 设备」两种预约类型，状态（待审核 / 已通过 / 已拒绝 / 已取消）与后台定时任务保持一致。

![我的预约](docs/images/07-my-reservation.png)

---

## 功能清单

### 业务功能

| 模块 | 能力 | 角色 |
| --- | --- | --- |
| 认证 | 注册、登录、JWT 鉴权、修改密码 | 全部 |
| 个人中心 | 资料查看与编辑、头像上传 | 全部 |
| 实验室 | 分页查询、关键字搜索、开放状态；管理端增删改 | 学生 / 管理员 |
| 设备 | 按实验室查询设备、规格与数量；管理端增删改 | 学生 / 管理员 |
| 预约 | 创建（实验室整间 / 指定设备）、列表、取消 | 学生 |
| 审核 | 待审核列表、通过 / 拒绝 | 管理员 |
| 用户管理 | 分页查询、编辑、删除、禁用 | 管理员 |
| 定时任务 | 每 60s 扫描过期待审核预约，自动置为「已取消」 | 系统 |

### AI 功能

| 能力 | 说明 |
| --- | --- |
| 规则问答（RAG） | 知识库文档切分入库，检索 Top-K 后按相似度阈值过滤，只把高相关内容喂给模型 |
| 业务数据查询 | 直接查库拿真实的实验室、设备、预约，杜绝编造 ID |
| 预约落库 | 复用 `reservation_service.create_reservation`，所有业务校验照常执行 |
| 取消预约 | 先查本人预约拿到 ID，复述后确认，再提交取消 |
| 日期换算 | `get_today` 提供服务器真实日期，"明天/后天"不再靠模型猜 |
| 过程可视化 | SSE 推送 `tool_start / tool_end / token`，前端逐条展示「正在检索知识库…」 |
| 安全渲染 | `marked` + `DOMPurify` 渲染 Markdown，防 XSS |

---

## 系统架构

```mermaid
flowchart LR
    subgraph Client["浏览器"]
        V["Vue 3 + Element Plus<br/>Vue Router / Axios"]
        C["AI 对话窗口<br/>fetch + ReadableStream"]
    end

    subgraph Server["FastAPI 应用"]
        R["API 路由层<br/>/api/auth · lab · equipment<br/>reservation · user · files · ai"]
        S["Service 业务层<br/>参数校验 / 冲突检测 / 状态机"]
        A["Agent 服务<br/>LangGraph StateGraph"]
        K["知识库服务<br/>Chroma + bge-small-zh"]
        T["后台任务<br/>60s 过期扫描"]
    end

    subgraph Infra["基础设施"]
        DB[("MySQL 8.0<br/>users / labs / equipments / reservations")]
        CH[("ChromaDB<br/>data/chroma")]
        LLM["OpenAI 兼容 LLM<br/>(DeepSeek 等)"]
        FS["本地文件存储<br/>uploads/"]
    end

    V -->|"REST + JWT"| R
    C -->|"SSE 流式"| R
    R --> S
    R --> A
    A -->|"工具调用"| S
    A -->|"检索"| K
    A -->|"chat/completions"| LLM
    S --> DB
    K --> CH
    T --> DB
    R --> FS
```

关键点：**Agent 没有直接操作数据库的通道**。它的 7 个工具全部是 `services` 层的薄封装，只能经由业务层读写数据，因此权限判断（`current_user`）、状态校验、时段冲突检测对 AI 路径同样生效。

---

## 核心流程

### 人工预约（前端表单）

```mermaid
sequenceDiagram
    actor U as 学生
    participant FE as 前端
    participant API as 预约接口
    participant SVC as 业务层
    participant DB as MySQL

    U->>FE: 选择实验室 / 设备
    FE->>API: POST /api/reservation
    API->>SVC: create_reservation(user, data)
    SVC->>SVC: 日期不早于今天、结束>开始
    SVC->>SVC: 实验室开放时间区间校验
    SVC->>SVC: 设备存在且非维修中
    SVC->>DB: 查询同时段重叠预约（status ∈ 0,1）
    alt 时段冲突
        SVC-->>FE: 该时段已被预约
    else 校验通过
        SVC->>DB: INSERT status=0（待审核）
        SVC-->>FE: 提交成功
        U->>API: 管理员审核 → status=1 / 2
    end
```

时段冲突用半开区间重叠判定，一条 SQL 覆盖：

```python
Reservation.start_time < data.end_time,
Reservation.end_time   > data.start_time,
Reservation.status.in_([0, 1]),   # 待审核和已通过都占位
```

预约状态机：

```mermaid
stateDiagram-v2
    state "待审核 status=0" as PENDING
    state "已通过 status=1" as APPROVED
    state "已拒绝 status=2" as REJECTED
    state "已取消 status=3" as CANCELLED

    [*] --> PENDING: 学生提交
    PENDING --> APPROVED: 管理员审核通过
    PENDING --> REJECTED: 管理员拒绝
    PENDING --> CANCELLED: 本人取消 / 超时自动取消
    APPROVED --> [*]
    REJECTED --> [*]
    CANCELLED --> [*]
```

> 「超时自动取消」由 `lifespan` 启动的后台协程负责，`asyncio.to_thread` 包住同步 SQLAlchemy 操作避免阻塞事件循环，每 60 秒扫一轮，把 `date < today` 或当天已过 `end_time` 的待审核单置为已取消。

### Agent 预约（自然语言）

```mermaid
sequenceDiagram
    actor U as 用户
    participant FE as 对话窗口
    participant API as /api/ai/chat/stream
    participant G as LangGraph
    participant L as LLM
    participant T as 工具层
    participant DB as MySQL

    U->>FE: "帮我预约后天下午的光学实验台"
    FE->>API: POST (messages[], Bearer token)
    API->>G: astream_events(recursion_limit=10)
    G->>L: system prompt + 历史消息
    L-->>FE: tool_start: get_today
    G->>T: get_today()
    T-->>G: "2026-11-26"
    L-->>FE: tool_start: list_open_labs
    G->>T: list_open_labs(keywords="有机化学")
    T->>DB: 查 status=1 的实验室
    DB-->>T: lab_id=3「化学实验室-有机」
    L-->>FE: tool_start: list_lab_equipments
    T->>DB: 查 lab_id=3 的设备
    L-->>FE: token: "后天是 2026-11-28，请确认预约信息…"
    U->>FE: "确认"
    L-->>FE: tool_start: create_lab_reservation
    G->>T: create_lab_reservation(lab_id, equipment_id, date, start, end)
    T->>DB: INSERT status=0
    L-->>FE: token: "预约已提交，状态待审核"
```

三个约束被写进 System Prompt，避免模型"自作主张"：

1. 提到今天/明天/后天，必须先调 `get_today`，不许自己推算日期；
2. 提交前必须复述实验室 ID 与名称（或设备 ID 与名称）、日期、起止时间；
3. 用户未明确回复"确认/确认预约/就这样预约"之前，禁止调用 `create_lab_reservation`。

---

## AI Agent 设计

### 图结构

```mermaid
flowchart LR
    START([START]) --> AG["agent 节点<br/>LLM + bind_tools"]
    AG -->|"有 tool_call"| TN["tools 节点<br/>ToolNode"]
    AG -->|"无 tool_call"| END([END])
    TN --> AG
```

典型 ReAct 循环，用 LangGraph 的 `MessagesState` + `tools_condition` 表达。`recursion_limit=10` 防止模型陷入无限工具调用。

### 工具清单

| 工具 | 作用 | 关键实现 |
| --- | --- | --- |
| `search_lab_docs` | 检索实验室规则知识库 | Chroma query + 相似度阈值过滤 |
| `list_open_labs` | 查询开放中的实验室 | 复用 `lab_service`，`status=1` |
| `list_lab_equipments` | 查询某实验室的设备 | 复用 `equipment_service` |
| `create_lab_reservation` | 创建预约并落库 | 复用 `reservation_service`，全部业务校验生效 |
| `get_today` | 返回服务器当前日期 | 解决"后天是哪天" |
| `list_my_reservations` | 查本人预约，拿取消所需的 ID | 强制 `user_id = current_user.id` |
| `cancel_lab_reservation` | 取消预约 | 校验归属与状态，仅待审核可取消 |

工具全部以 `@tool` 装饰器定义，用闭包捕获 `db` 与 `current_user`——这样每个请求的工具实例都绑定当前登录用户，天然满足数据隔离，不需要模型传 `user_id`（传了也不可信）。

### RAG 知识库

| 项 | 取值 |
| --- | --- |
| 文档 | `backend/data/kb/*.md`：安全规范、开放时间、设备使用、预约规则 |
| 切分策略 | 一篇文档一条向量（文档本身短，约 4~6 行，切碎反而丢上下文） |
| 向量模型 | `BAAI/bge-small-zh-v1.5`（sentence-transformers 本地推理） |
| 向量库 | ChromaDB PersistentClient，集合 `lab_kb`，落盘 `data/chroma` |
| 检索 | Top-5 → `score = 1/(1+distance)` → 阈值 0.5 → 取前 2 条拼进上下文 |
| 冷启动 | 模型加载约 15s，已用 `lifespan` 在启动阶段 `warmup()` 预热，避免首个请求超时 |

检索结果会带上来源文件名（`[安全规范.md]`），让回答可溯源；相似度低于阈值直接丢弃，宁可不答也不喂噪声。

### SSE 事件协议

后端把 Agent 的执行过程翻译成 5 类事件，一条一条 `data: {...}\n\n` 推出去：

| type | 载荷 | 前端表现 |
| --- | --- | --- |
| `status` | `message` | 显示"正在思考…" |
| `tool_start` | `name` / `label` | 「· 开始：查询开放实验室」 |
| `tool_end` | `name` / `label` / `preview` | 「· 完成」+ 结果预览（截断 200 字） |
| `token` | `content` | 逐字追加到气泡 |
| `error` / `done` | `message` | 收尾 |

配合响应头 `X-Accel-Buffering: no`，避免反向代理把整段流缓存后一次性吐出。

---

## 技术栈

**后端**

| 组件 | 版本 | 用途 |
| --- | --- | --- |
| FastAPI | 0.115 | Web 框架、依赖注入、自动 OpenAPI |
| Uvicorn | 0.34 | ASGI 服务器 |
| SQLAlchemy | 2.0 | ORM（`Mapped` / `mapped_column` 声明式模型） |
| PyMySQL + cryptography | 1.1 / 50.0 | MySQL 驱动，支持 `caching_sha2_password` |
| Pydantic-Settings | 2.7 | `.env` 配置加载 |
| PyJWT | 2.13 | HS256 签发/校验 token |
| bcrypt | 5.0 | 密码哈希（不存明文） |
| LangGraph | 1.x | Agent 图编排 |
| langchain-openai | 1.6 | OpenAI 兼容客户端（DeepSeek 等） |
| ChromaDB | 1.5 | 向量库 |
| sentence-transformers | 6.0 | 中文 embedding 推理 |

**前端**

| 组件 | 版本 | 用途 |
| --- | --- | --- |
| Vue | 3.5 | `<script setup>` 组合式 API |
| Vite | 8.x | 开发服务器与构建 |
| Vue Router | 5.x | 路由 + 全局守卫 |
| Element Plus | 2.14 | UI 组件库 |
| Axios | 1.20 | REST 请求，统一拦截器注入 token |
| marked + DOMPurify | 18 / 3.4 | Markdown 渲染 + XSS 过滤 |

---

## 数据模型

```mermaid
erDiagram
    USERS ||--o{ RESERVATIONS : "发起"
    LABS ||--o{ EQUIPMENTS : "包含"
    LABS ||--o{ RESERVATIONS : "被预约"
    EQUIPMENTS ||--o{ RESERVATIONS : "被预约(可空)"

    USERS {
        int id PK
        string username "账号"
        string password "bcrypt 哈希"
        string name "姓名"
        string role "student / admin"
        int status "0 禁用 1 正常"
    }
    LABS {
        int id PK
        string name
        string location
        int capacity
        string open_time
        string close_time
        int status "0 关闭 1 开放"
    }
    EQUIPMENTS {
        int id PK
        int lab_id FK
        string name
        string spec "型号规格"
        int quantity
        int status "0 维修 1 正常"
    }
    RESERVATIONS {
        int id PK
        int user_id FK
        int lab_id FK
        int equipment_id FK "空=整间实验室"
        string date
        string start_time
        string end_time
        int status "0 待审 1 通过 2 拒绝 3 取消"
        string remark
    }
```

`reservations.equipment_id` 为空表示预约整间实验室，非空表示预约某台设备——两种预约共用一张表，用 `type` 字段在响应里派生为「实验室 / 设备」。

---

## 目录结构

```text
Laboratory Reservation_System_agent/
├── backend/
│   ├── app/
│   │   ├── api/                # 路由层：auth / user / lab / equipment / reservation / files / ai
│   │   ├── services/           # 业务层：校验、状态机、Agent、RAG
│   │   │   ├── agent_service.py    # LangGraph 图 + SSE 事件流
│   │   │   ├── agent_tools.py      # 7 个工具定义
│   │   │   ├── kb_service.py       # Chroma 向量库与检索
│   │   │   └── reservation_service.py  # 预约规则 + 过期扫描
│   │   ├── models/             # SQLAlchemy ORM
│   │   ├── schemas/            # Pydantic 请求/响应模型
│   │   ├── dependencies/       # get_current_user / get_current_admin
│   │   ├── common/             # 统一响应体、异常与处理器
│   │   ├── config.py           # 配置与上传限制
│   │   ├── database.py         # engine / SessionLocal / Base
│   │   └── main.py             # 应用装配、CORS、异常注册、lifespan
│   ├── data/
│   │   ├── kb/                 # 知识库 Markdown（4 篇）
│   │   └── chroma/             # 向量库持久化目录
│   ├── uploads/                # 上传文件（已 gitignore）
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── views/              # 13 个页面：登录/注册/首页/实验室/设备/预约/AI 对话/审核…
│   │   ├── api/                # 与后端一一对应的请求封装
│   │   ├── router/             # 路由表 + token 守卫
│   │   ├── layouts/            # 侧边栏布局
│   │   ├── components/         # ReserveDialog 等复用组件
│   │   └── utils/              # request 拦截器、token 存取
│   ├── .env.development        # VITE_API_BASE_URL
│   └── package.json
└── docs/images/                # README 截图
```

---

## 快速开始

### 环境要求

- Python 3.11+
- Node.js 22.18+ 或 24.12+
- MySQL 8.0+

### 1. 准备数据库

```sql
CREATE DATABASE lab_reservation DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

建表不需要手动执行 DDL——应用启动时 `Base.metadata.create_all()` 会自动建表。

### 2. 配置后端环境变量

在 `backend/` 下创建 `.env`（该文件已被 gitignore，不会进版本库）：

```dotenv
# 数据库
DATABASE_URL=mysql+pymysql://root:your_password@127.0.0.1:3306/lab_reservation?charset=utf8mb4

# JWT
JWT_SECRET_KEY=please-change-this-to-a-random-string
JWT_EXPIRE_HOURS=24
JWT_ALGORITHM=HS256

# 大模型（任意 OpenAI 兼容端点均可）
LLM_API_KEY=sk-xxxxxxxx
LLM_MODEL=your-model-name
LLM_BASE_URL=https://api.deepseek.com/v1
```

> `LLM_BASE_URL` 指向任何兼容 `chat/completions` 与 tool calling 的服务即可（DeepSeek、通义、Moonshot、vLLM 自建等）。若使用不支持 `thinking` 参数的模型，注意 `agent_service.py` 中的 `extra_body={"thinking": {"type": "disabled"}}` 需相应调整。

### 3. 启动后端

```bash
cd backend

python -m venv .venv
source .venv/Scripts/activate      # Windows Git Bash
# .venv\Scripts\activate           # Windows CMD / PowerShell
# source .venv/bin/activate        # macOS / Linux

pip install -r requirements.txt

uvicorn app.main:app --reload --port 8000
```

首次启动会做两件耗时的事：下载 `bge-small-zh-v1.5` 模型（约 100MB，代码里已默认走 `hf-mirror.com` 镜像），并把 4 篇知识库文档灌入 Chroma。后续启动只做向量检索预热。

- 接口文档：<http://127.0.0.1:8000/docs>
- 静态资源：`http://127.0.0.1:8000/uploads/<filename>`

### 4. 启动前端

```bash
cd frontend
npm install
npm run dev
```

访问 <http://localhost:5173>。后端 CORS 已放行 `5173`，前端 `VITE_API_BASE_URL` 指向 `http://127.0.0.1:8000`。

### 5. 初始化数据

注册一个账号后，需要管理员身份才能审核预约、维护实验室。直接把该用户的 `role` 改成 `admin`：

```sql
UPDATE users SET role = 'admin' WHERE username = 'your_account';
```

实验室与设备数据可通过管理端页面录入，或直接写库。设备必须挂在一个已存在的 `lab_id` 下。

---

## 接口一览

| 方法 | 路径 | 说明 | 权限 |
| --- | --- | --- | --- |
| POST | `/api/auth/register` | 注册 | 公开 |
| POST | `/api/auth/login` | 登录，返回 token | 公开 |
| GET | `/api/user/me` | 当前用户信息 | 登录 |
| PUT | `/api/user/me` | 更新个人信息 | 登录 |
| PUT | `/api/user/password` | 修改密码 | 登录 |
| GET | `/api/user/list` | 用户分页查询 | 管理员 |
| POST | `/api/user` | 新增用户 | 管理员 |
| PUT / DELETE | `/api/user/{id}` | 编辑 / 删除用户 | 管理员 |
| GET | `/api/lab/list` | 实验室分页查询 | 登录 |
| GET | `/api/lab/{id}` | 实验室详情 | 登录 |
| POST / PUT | `/api/lab` · `/api/lab/{id}` | 新增 / 更新实验室 | 管理员 |
| GET | `/api/equipment/list` | 设备分页查询 | 登录 |
| POST / PUT / DELETE | `/api/equipment` · `/api/equipment/{id}` | 新增 / 更新 / 删除设备 | 管理员 |
| GET | `/api/reservation/list` | 预约列表（学生仅本人） | 登录 |
| POST | `/api/reservation` | 创建预约 | 登录 |
| PUT | `/api/reservation/{id}/cancel` | 取消预约 | 本人 |
| PUT | `/api/reservation/{id}/audit` | 审核预约 | 管理员 |
| POST | `/api/files/upload` | 文件 / 头像上传 | 登录 |
| POST | `/api/ai/chat/stream` | Agent 对话（SSE） | 登录 |

---

## 实现成果

**跑通的完整链路**

从截图可以逐帧对上，一条自然语言指令确实完成了过去需要点五六次页面的操作：

1. **规则问答可信**：问"进入实验室要注意什么"，回答里出现了知识库原文的着装、禁食、设备故障、离场四类要求，并明确"开放时间内也需先预约并审核通过才能进入"——这句是 `开放时间.md` 里的原话，模型没有自由发挥。
2. **参数不再编造**：用户说"有机化学实验室"，Agent 发现库里没有这个名字，自己收敛到「化学实验室-有机」（`lab_id=3`），并给出真实的设备 ID 9~12。这些 ID 后续被 `create_lab_reservation` 直接使用且成功落库，说明不是模拟值。
3. **日期不靠猜**：`get_today` 返回 2026-11-26，"后天"被正确换算为 2026-11-28（周六），并带上星期几，让用户能察觉日期是否选错。
4. **人机确认闭环**：预约与取消都执行「复述 → 等确认 → 才落库」，取消时先 `list_my_reservations` 拿到 `reservation_id=20`，避免模型臆造 ID 导致误删。
5. **状态与后台一致**：Agent 提交后提示"当前状态为待审核"，与「我的预约」列表里的状态、以及 60s 过期扫描任务保持同一套状态机。

**工程层面的沉淀**

| 问题 | 处理方式 |
| --- | --- |
| 模型加载 15s 导致首问超时 | 用 `lifespan` 启动阶段 `warmup()` 预热，把冷启动成本前移 |
| Agent 输出被 JSON 淹没 | 工具结果统一走 `_tool_output_preview` 截断，最长 200 字，人看的和模型看的分离 |
| 长连接被代理缓存 | SSE 响应头 `Cache-Control: no-cache` + `X-Accel-Buffering: no` |
| Markdown 渲染 XSS | `marked` 输出再过一层 `DOMPurify` |
| 前端 120s 超时 | 改为流式后首个 token 秒级返回，超时压力消失 |
| 同步 ORM 阻塞事件循环 | 后台扫描与 embedding 预热都包 `asyncio.to_thread` |
| AI 越权 | 工具闭包绑定 `current_user`，模型无法指定他人身份 |



