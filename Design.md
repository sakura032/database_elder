# 项目设计与实现说明

## 1. 设计依据

本项目以用户提供的手绘完整 ER 图为唯一业务建模标准

## 2. 手绘 ER 图核心实体

| 实体 | 数据库表 | 说明 |
|---|---|---|
| 老年人 | `elderly` | 老人基础信息 |
| 服务需求 | `service_demand` | 老人提交的服务申请 |
| 服务记录 | `service_record` | 服务过程记录，从需求被分派给机构时生成，服务完成后补全执行内容 |
| 服务人员 | `service_staff` | 机构下属服务人员 |
| 服务机构 | `service_org` | 养老服务机构 |
| 社区 | `community` | 社区基础信息 |

## 3. 最终业务主线

```text
老人登录
  -> 提交服务需求
  -> 系统生成“待分派”需求
  -> 社区端将需求分派给服务机构
  -> 系统创建“未完成”的服务过程记录
  -> 机构端为服务过程记录安排具体服务人员
  -> 机构端补全服务记录并标记服务完成
  -> 老人在服务记录中填写评价
  -> 需求流程结束
```

服务需求状态流转：

```text
待分派 -> 已分派 -> 已匹配 -> 已完成 -> 已评价
```

服务记录状态流转：

```text
未完成 -> 已完成
```

状态与数据操作对应关系：

| 阶段 | 操作说明 | `service_demand.demand_status` | `service_record.record_status` |
|---|---|---|---|
| 老人提交需求 | 新增 `service_demand` | 待分派 | 无服务记录 |
| 社区分派机构 | 新增 `service_record`，写入 `demand_id`、`org_id` | 已分派 | 未完成 |
| 机构安排人员 | 向 `staff_record_relation` 写入服务人员和服务记录关系 | 已匹配 | 未完成 |
| 机构完成服务 | 补全 `service_record` 的服务时间、时长、类型等信息 | 已完成 | 已完成 |
| 老人填写评价 | 更新 `service_record.service_evaluation` | 已评价 | 已完成 |

服务需求优先级规则：

| 紧急程度 | 业务含义 | 系统使用方式 |
|---|---|---|
| 紧急 | 需要优先分派和执行的服务需求 | 社区端待分派列表置顶，机构端未完成服务置顶，AI 推荐机构优先考虑空闲人员和低负载 |
| 较急 | 比普通需求更需要尽快处理 | 排序优先于普通需求，统计中计入高优先级待分派服务 |
| 普通 | 常规养老服务需求 | 按提交时间和流程状态正常处理 |

`service_demand.emergency_level` 不改变“待分派 -> 已分派 -> 已匹配 -> 已完成 -> 已评价”的状态流转，但会影响列表排序、颜色标识、AI 推荐依据、自然语言查库结果和社区端统计风险提示。


## 4.  ER 图核心关系

最终关系确定为：
```text
elderly 1:N service_demand
service_demand 1:N service_record
service_org 1:N service_record
service_record M:N service_staff
service_org 1:N service_staff
community 1:N service_org
```

| 关系 | 当前实现 | 基数 |
|---|---|---|
| 老年人提交服务需求 | `service_demand.elderly_id -> elderly.elderly_id` | 1:N |
| 服务需求匹配服务记录 | `service_record.demand_id -> service_demand.demand_id` | 1:N |
| 服务机构承接服务记录 | `service_record.org_id -> service_org.org_id` | N:1 |
| 服务人员属于服务机构 | `service_staff.org_id -> service_org.org_id` | N:1 |
| 服务机构属于社区 | `service_org.community_id -> community.community_id` | N:1 |
| 服务人员执行服务记录 | `staff_record_relation(staff_id, record_id)` | M:N |


## 5. 数据库当前情况

系统默认连接远程数据库 `pension1_service`：

```text
DB_HOST = 192.168.70.82
DB_PORT = 3306
DB_NAME = pension1_service
```

已确认远程数据库中存在以下业务表。数据量会随注册、测试和业务操作变化，实时数量以数据库查询结果为准。

| 表名 | 数据量 | 说明 |
|---|---:|---|
| `community` | 以数据库为准 | 社区信息 |
| `elderly` | 以数据库为准 | 老年人信息 |
| `service_demand` | 以数据库为准 | 服务需求 |
| `service_org` | 以数据库为准 | 服务机构 |
| `service_staff` | 以数据库为准 | 服务人员 |
| `service_record` | 以数据库为准 | 服务过程记录 |
| `staff_record_relation` | 以数据库为准 | 服务人员与服务记录关联 |
| `user_account` | 以数据库为准 | 登录账号与角色权限表 |


## 6. 三个账号角色设计

`user_account` 字段：

| 字段 | 含义 |
|---|---|
| `account_id` | 账号主键 |
| `username` | 登录用户名 |
| `password_hash` | 哈希密码 |
| `role` | 角色：社区管理员为 `community_admin`，机构为 `org`，老人为 `elder` |
| `subject_id` | 绑定业务实体 ID |
| `display_name` | 显示名称 |
| `status` | 账号状态 |
| `created_at` | 创建时间 |
| `updated_at` | 更新时间 |

密码说明：
- 远程库已有账号可能使用 bcrypt 哈希，格式通常以 `$2a$`、`$2b$` 或 `$2y$` 开头。
- 新注册和修改密码使用 Werkzeug PBKDF2 哈希。
- 后端登录校验已同时兼容 bcrypt 和 Werkzeug 哈希。


绑定规则 三个登录角色：

| 端口 | 角色值 | 绑定实体 | 角色定位 | 核心权责 |
|---|---|---|---|---|
| 老年人端 | `elder` | `elderly.elderly_id` | 服务需求发起者、服务接受者 | 提交需求、查看进度、查看自己的服务记录、填写评价 |
| 机构端 | `org` | `service_org.org_id` | 服务提供方、服务执行管理方 | 管理本机构服务人员、查看本机构服务过程记录、安排服务人员、补全服务记录 |
| 社区端 | `community_admin` | `community.community_id` | 全局管理员、监管方 | 管理辖区基础信息、分派需求、监管服务、查看统计 |

说明：
- 服务记录由机构端补全录入，并在记录中选择具体服务人员。
- 数据库、后端权限判断和前端页面统一只使用 `community_admin`、`org`、`elder` 三类角色；`/admin/...` 仅作为社区端接口路径前缀保留。
- 公共注册权限收口：只允许注册老人账号，注册页只填写用户名和密码；系统自动生成 `elderly.elderly_id`，同步创建老人基础档案并写入 `user_account.subject_id`。社区管理员账号和机构账号由数据库管理员按实际社区、机构主体预置。
- 登录页保留“社区端 / 机构端 / 老人端”三个端口选择，端口选择用于校验 `user_account.role`，不再提供默认账号或自动填充密码。

## 7. 接口按角色重做

业务接口采用：

```text
/角色/对象/动作
```

公共认证接口使用：

```text
/auth/login
/auth/logout
/auth/register
/auth/me
/auth/password/update
```

### 7.1 各端核心动作

| 端口 | 核心动作 | 业务结果 |
|---|---|---|
| 老人端 | 提交服务需求 | `service_demand` 新增记录，状态为 `待分派` |
| 社区端 | 分派需求给机构 | `service_record` 新增未完成记录，需求状态变为 `已分派`；待分派列表按紧急程度优先展示 |
| 机构端 | 为服务记录安排人员 | `staff_record_relation` 新增关系，需求状态变为 `已匹配`；未完成服务按紧急程度优先展示 |
| 机构端 | 补全服务记录 | `service_record.record_status` 变为 `已完成`，需求状态变为 `已完成` |
| 老人端 | 填写服务评价 | `service_record.service_evaluation` 写入评价，需求状态变为 `已评价` |

老人端接口：

| 接口 | 方法 | 功能 | 主要涉及表 |
|---|---|---|---|
| `/elder/home/summary` | GET | 老人首页概览 | `elderly`, `service_demand`, `service_record` |
| `/elder/profile/select` | GET | 查看个人信息 | `elderly` |
| `/elder/demand/create` | POST | 提交服务需求 | `service_demand` |
| `/elder/demand/select` | GET | 查看自己的需求进度 | `service_demand` |
| `/elder/record/select` | GET | 查看自己的服务记录 | `service_record`, `service_demand` |
| `/elder/record/evaluate` | POST | 填写服务评价 | `service_record`, `service_demand` |

机构端接口：

| 接口 | 方法 | 功能 | 主要涉及表 |
|---|---|---|---|
| `/org/home/summary` | GET | 机构首页概览 | `service_org`, `service_record`, `service_staff` |
| `/org/profile/select` | GET | 查看机构信息 | `service_org`, `community` |
| `/org/staff/select` | GET | 查看本机构服务人员 | `service_staff` |
| `/org/staff/create` | POST | 新增本机构服务人员 | `service_staff` |
| `/org/staff/update` | POST | 修改本机构服务人员 | `service_staff` |
| `/org/record/select` | GET | 查看本机构服务过程记录 | `service_record`, `service_demand`, `elderly` |
| `/org/record/staff/assign` | POST | 为服务记录安排服务人员 | `staff_record_relation`, `service_demand` |
| `/org/record/complete` | POST | 补全服务记录并标记完成 | `service_record`, `service_demand` |

社区端接口：

| 接口 | 方法 | 功能 | 主要涉及表 |
|---|---|---|---|
| `/admin/home/summary` | GET | 社区端首页统计 | 全部核心表 |
| `/admin/elder/select` | GET | 查看老人信息 | `elderly` |
| `/admin/org/select` | GET | 查看机构信息 | `service_org`, `community` |
| `/admin/staff/select` | GET | 查看服务人员信息 | `service_staff`, `service_org` |
| `/admin/demand/select` | GET | 查看服务需求 | `service_demand`, `elderly` |
| `/admin/demand/assign` | POST | 分派需求给机构，并创建未完成服务记录 | `service_demand`, `service_record` |
| `/admin/record/select` | GET | 查看服务过程记录 | `service_record`, `service_demand`, `elderly`, `service_org`, `service_staff` |

AI 接口：

| 接口 | 方法 | 权限 | 功能 | 说明 |
|---|---|---|---|---|
| `/ai/chat` | POST | `elder`、`community_admin`、`org` | 统一 AI 聊天入口 | 前端右下角聊天框使用，根据自然语言判断意图 |
| `/ai/elder/demand/parse` | POST | `elder` | 老人端需求识别 | 输入自然语言，返回服务类型、紧急程度、描述 |
| `/ai/admin/demand/recommend-org` | POST | `community_admin` | 推荐承接机构 | 基于需求、老人、机构能力和机构负载推荐 |
| `/ai/admin/report/summary` | GET | `community_admin` | 生成统计报告 | 基于 SQL 统计结果生成社区端运营分析 |
| `/ai/query` | POST | `elder`、`community_admin`、`org` | 自然语言查库 | 模型只识别查询意图，后端只执行白名单 SQL |
| `/ai/org/record/recommend-staff` | POST | `org` | 推荐服务人员 | 基于当前机构的服务记录和服务人员状态推荐 |
| `/ai/org/record/draft` | POST | `org` | 服务记录草稿 | 根据机构端自然语言输入生成服务记录字段 |
| `/ai/action/confirm` | POST | `elder`、`community_admin`、`org` | 确认执行 AI 待操作 | 后端按 action_id 校验账号、角色、主体和参数后执行写库 |
| `/ai/action/cancel` | POST | `elder`、`community_admin`、`org` | 取消 AI 待操作 | 只允许创建该动作的当前登录用户取消 |

AI 辅助功能与安全控制：

| 使用端 | AI 功能 | 业务作用 |
|---|---|---|
| 老人端 | 需求识别、服务查询、评价辅助 | 将自然语言描述整理为服务类型、紧急程度和需求描述，辅助老人提交需求、查询进度和整理评价内容 |
| 社区端 | 机构推荐、统计报告、监管查询 | 根据需求紧急程度、机构能力、空闲人员和服务负载推荐承接机构，并生成社区运营统计摘要 |
| 机构端 | 服务人员推荐、服务记录草稿、记录查询 | 根据服务记录和本机构人员状态推荐执行人员，并把服务过程描述整理为规范记录字段 |

AI 写库动作采用“识别/推荐 -> 表单回填 -> 用户确认 -> 后端校验 -> 数据库写入”的闭环控制。系统不会因为模型返回结果而直接修改数据库；涉及提交需求、分派机构、安排人员、完成记录和提交评价的操作，都会生成待确认动作，并在用户明确确认后由后端再次校验角色、主体归属和业务参数。

自然语言查库采用白名单查询方式：模型只负责识别查询意图和关键词，实际 SQL 由后端预设函数执行。该设计避免模型直接生成 SQL，同时保证老人只能查询本人数据、机构只能查询本机构数据、社区端才能查询全局监管数据。

统计报告和推荐结果都以数据库真实数据为基础。紧急程度、机构负载、空闲人员数量、未完成记录数量等指标会参与推荐和排序，最终结果作为页面辅助决策信息展示，用户仍通过标准业务按钮或确认流程完成操作。

## 8. 接口清单

| 接口 | 方法 | 权限 | 涉及表 | SQL 类型 |
|---|---|---|---|---|
| `/auth/login` | POST | 全部 | `user_account` | SELECT |
| `/auth/logout` | POST | 已登录 | Session | - |
| `/auth/register` | POST | 全部，限老人 | `user_account`, `elderly` | 自动创建老人档案和老人账号 |
| `/auth/me` | GET | 已登录 | Session | - |
| `/auth/password/update` | POST | 已登录 | `user_account` | SELECT/UPDATE |
| `/admin/home/summary` | GET | 社区管理员 | 全部核心表 | SELECT |
| `/admin/elder/select` | GET | 社区管理员 | `elderly` | SELECT |
| `/admin/demand/select` | GET | 社区管理员 | `service_demand`, `elderly` | SELECT |
| `/admin/org/select` | GET | 社区管理员 | `service_org`, `community` | SELECT |
| `/admin/staff/select` | GET | 社区管理员 | `service_staff`, `service_org` | SELECT |
| `/admin/demand/assign` | POST | 社区管理员 | `service_demand`, `service_record` | INSERT/UPDATE |
| `/admin/record/select` | GET | 社区管理员 | `service_record` 等 | SELECT |
| `/org/home/summary` | GET | 机构 | `service_org`, `service_record`, `service_staff` | SELECT |
| `/org/profile/select` | GET | 机构 | `service_org`, `community` | SELECT |
| `/org/staff/select` | GET | 机构 | `service_staff` | SELECT |
| `/org/staff/create` | POST | 机构 | `service_staff` | INSERT |
| `/org/staff/update` | POST | 机构 | `service_staff` | UPDATE |
| `/org/record/select` | GET | 机构 | `service_record`, `service_demand`, `elderly` | SELECT |
| `/org/record/staff/assign` | POST | 机构 | `staff_record_relation`, `service_demand` | INSERT/UPDATE |
| `/org/record/complete` | POST | 机构 | `service_record`, `service_demand` | UPDATE |
| `/elder/home/summary` | GET | 老人 | `elderly`, `service_demand`, `service_record` | SELECT |
| `/elder/profile/select` | GET | 老人 | `elderly` | SELECT |
| `/elder/demand/select` | GET | 老人 | `service_demand` | SELECT |
| `/elder/demand/create` | POST | 老人 | `service_demand` | INSERT |
| `/elder/record/select` | GET | 老人 | `service_record` 等 | SELECT |
| `/elder/record/evaluate` | POST | 老人 | `service_record`, `service_demand` | UPDATE |
| `/ai/chat` | POST | 老人、社区管理员、机构 | 按意图读取相关表 | SELECT / AI 调用 |
| `/ai/elder/demand/parse` | POST | 老人 | 无直接写库 | AI 调用 |
| `/ai/admin/demand/recommend-org` | POST | 社区管理员 | `service_demand`, `elderly`, `service_org`, `service_staff`, `service_record` | SELECT / AI 调用 |
| `/ai/admin/report/summary` | GET | 社区管理员 | 全部核心表统计 | SELECT / AI 调用 |
| `/ai/query` | POST | 老人、社区管理员、机构 | 按角色读取预设查询表 | SELECT / AI 调用 |
| `/ai/org/record/recommend-staff` | POST | 机构 | `service_record`, `service_demand`, `elderly`, `service_staff`, `staff_record_relation` | SELECT / AI 调用 |
| `/ai/org/record/draft` | POST | 机构 | `service_record`, `service_demand`, `elderly` | SELECT / AI 调用 |
| `/ai/action/confirm` | POST | 老人、社区管理员、机构 | 按待执行动作类型访问对应业务表 | 后端确认后 INSERT/UPDATE |
| `/ai/action/cancel` | POST | 老人、社区管理员、机构 | 内存待执行动作 | 无写库 |

## 9. 后端实现结构

```text
web      负责接口
models   负责 SQL
validate 负责参数校验
ai       负责 DeepSeek 调用、提示词和 AI 结果校正
static   负责 Vue + ECharts 页面
```

当前采用 Flask-Login 管理登录状态，Flask-CORS 支持跨域请求，WTForms 校验请求参数，bcrypt 用于兼容远程库已有账号密码哈希。AI 层使用 Python 标准库 `urllib` 直连 DeepSeek OpenAI 兼容接口，不引入额外 SDK。

## 10. 系统请求处理流程

系统采用前后端分离思路组织请求处理流程，整体链路如下：

```text
用户在 Vue 页面操作
  -> Axios 把请求发给 Flask 后端
  -> Flask 的 web 层接收请求
  -> validate 层检查参数是否合法
  -> web 层检查用户权限
  -> models 层用 PyMySQL 执行 SQL
  -> MySQL 返回查询/修改结果
  -> models 层整理成 dict
  -> Flask 返回 JSON
  -> Axios 收到 JSON
  -> Vue 更新页面
  -> ECharts 根据统计数据画图
```

职责链路：

```text
web -> validate -> 权限 -> models -> MySQL -> JSON -> Vue/ECharts
```

AI 请求链路：

```text
用户在 AI 聊天框输入自然语言
  -> Axios 调用 /ai/chat
  -> web/ai.py 校验登录角色和请求参数
  -> ai/service.py 判断意图
  -> models/ai.py 查询真实业务上下文
  -> ai/client.py 使用 urllib 调用 DeepSeek
  -> ai/service.py 校正模型返回字段
  -> Flask 返回 JSON
  -> Vue 回填表单或展示报告
  -> 如涉及写库动作，/ai/chat 同时返回后端生成的 pending_action
  -> 用户点击确认执行或回复明确确认词
  -> Vue 调用 /ai/action/confirm
  -> ai/actions.py 校验 action_id、账号、角色、绑定主体和过期时间
  -> 后端调用对应模型层函数完成提交、分派、安排或记录完成
```

## 11. 交付功能范围

- 系统连接远程 MySQL，默认数据库为 `192.168.70.82 / pension1_service`。
- 后端采用 Flask 蓝图分层，已实现认证、老人端、机构端、社区端和 AI 相关接口。
- 登录体系使用 `user_account`，角色固定为 `elder`、`org`、`community_admin`，并按 `subject_id` 绑定对应业务主体。
- 公共注册仅开放老人账号，注册后自动创建老人档案并绑定账号；社区管理员和机构账号由数据库预置。
- 旧 `staff` 登录角色和 `/staff/...` 旧接口已移除，服务人员只作为机构下属业务实体存在。
- 老人端已实现个人资料维护、服务需求提交、需求进度查看、服务记录查看和服务评价。
- 机构端已实现机构信息查看、服务人员管理、服务记录查看、多人员匹配和服务记录完成。
- 社区端已实现老人、机构、人员、需求、记录的全局监管查询，以及需求分派和服务过程记录创建。
- 前端采用 Vue + Axios + ECharts，通过单页工作台承载登录页、老人端、机构端和社区端页面。
- AI 能力已接入 DeepSeek 标准 HTTP 接口，覆盖需求识别、机构推荐、统计报告、自然语言查库、人员推荐和服务记录草稿。
- AI 写库动作采用后端托管的二次确认机制，用户明确确认后才执行提交、分派、安排人员、完成记录或评价写入。
- `service_demand.emergency_level` 已进入业务闭环，统一使用 `紧急 -> 较急 -> 普通` 排序和红、橙、绿视觉标识。

## 12. 前端页面结构

项目采用一个 Flask 静态入口承载四个页面视图：

| 页面 | 对应角色 | 主要功能 |
|---|---|---|
| 登录页 | 全部用户 | 登录、登出、读取当前账号信息，并按角色跳转 |
| 老人端页面 | `elder` | 提交需求、查看进度、查看服务记录、填写评价 |
| 机构端页面 | `org` | 查看机构信息、管理服务人员、安排服务人员、补全服务记录 |
| 社区端页面 | `community_admin` | 查看全量数据、分派需求、监管服务过程、查看统计 |
