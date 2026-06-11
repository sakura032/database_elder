# 项目设计与进度实现情况

## 1. 设计依据

本项目以用户提供的手绘完整 ER 图为唯一业务建模标准。开题 PPT 中的文字描述只作为项目背景参考，不作为当前数据库实现的最终依据。

## 2. 手绘 ER 图核心实体

| 实体 | 当前数据库表 | 说明 |
|---|---|---|
| 老年人 | `elderly` | 老人基础信息 |
| 服务需求 | `service_demand` | 老人提交的服务申请 |
| 服务记录 | `service_record` | 服务执行记录 |
| 服务人员 | `service_staff` | 机构下属服务人员 |
| 服务机构 | `service_org` | 养老服务机构 |
| 社区 | `community` | 社区基础信息 |

## 3. ER 图核心关系

| 关系 | 当前实现 | 基数 |
|---|---|---|
| 老年人提交服务需求 | `service_demand.elderly_id -> elderly.elderly_id` | 1:N |
| 老年人被服务形成服务记录 | `service_record.elderly_id -> elderly.elderly_id` | 1:N |
| 服务需求匹配服务记录 | `service_record.demand_id -> service_demand.demand_id` | 1:N |
| 服务人员属于服务机构 | `service_staff.org_id -> service_org.org_id` | N:1 |
| 服务机构属于社区 | `service_org.community_id -> community.community_id` | N:1 |
| 服务人员执行服务记录 | `staff_record_relation(staff_id, record_id)` | M:N |

## 4. 数据库当前情况

已确认远程数据库 `pension_service` 中存在以下业务表：

| 表名 | 数据量 | 说明 |
|---|---:|---|
| `community` | 3 | 社区信息 |
| `elderly` | 8 | 老年人信息 |
| `service_demand` | 16 | 服务需求 |
| `service_org` | 6 | 服务机构 |
| `service_staff` | 14 | 服务人员 |
| `service_record` | 10 | 服务记录 |
| `staff_record_relation` | 12 | 服务人员与服务记录关联 |

本阶段新增：

| 表名 | 说明 |
|---|---|
| `user_account` | 登录账号与角色权限表 |

## 5. 认证权限设计

`user_account` 字段：

| 字段 | 含义 |
|---|---|
| `account_id` | 账号主键 |
| `username` | 登录用户名 |
| `password_hash` | 哈希密码 |
| `role` | 角色：`admin`、`staff`、`elder` |
| `subject_id` | 绑定业务实体 ID |
| `display_name` | 显示名称 |
| `status` | 账号状态 |
| `created_at` | 创建时间 |
| `updated_at` | 更新时间 |

绑定规则：

| 角色 | 绑定表 |
|---|---|
| `admin` | `community.community_id` |
| `staff` | `service_staff.staff_id` |
| `elder` | `elderly.elderly_id` |

公共注册权限收口：只允许注册老人账号。管理员和机构人员账号由管理员预置或后续管理员端创建。

## 6. 接口命名规范

业务接口采用：

```text
/角色/对象/动作
```

示例：

```text
/admin/elder/select
/admin/demand/select
/staff/record/select
/elder/demand/select
```

公共认证接口使用：

```text
/auth/login
/auth/logout
/auth/register
/auth/me
/auth/password/update
```

## 7. 当前已实现接口

| 接口 | 方法 | 权限 | 涉及表 | SQL 类型 |
|---|---|---|---|---|
| `/auth/login` | POST | 全部 | `user_account` | SELECT |
| `/auth/logout` | POST | 已登录 | Session | - |
| `/auth/register` | POST | 全部，限老人 | `user_account`, `elderly` | SELECT/INSERT |
| `/auth/me` | GET | 已登录 | Session | - |
| `/auth/password/update` | POST | 已登录 | `user_account` | SELECT/UPDATE |
| `/admin/home/summary` | GET | 社区管理员 | 全部核心表 | SELECT |
| `/admin/elder/select` | GET | 社区管理员 | `elderly` | SELECT |
| `/admin/demand/select` | GET | 社区管理员 | `service_demand`, `elderly` | SELECT |
| `/admin/org/select` | GET | 社区管理员 | `service_org`, `community` | SELECT |
| `/admin/staff/select` | GET | 社区管理员 | `service_staff`, `service_org` | SELECT |
| `/admin/record/select` | GET | 社区管理员 | `service_record` 等 | SELECT |
| `/staff/home/summary` | GET | 机构人员 | `service_staff`, `service_org`, `community` | SELECT |
| `/staff/org/select` | GET | 机构人员 | `service_staff`, `service_org`, `community` | SELECT |
| `/staff/demand/select` | GET | 机构人员 | `service_demand`, `elderly` | SELECT |
| `/staff/record/select` | GET | 机构人员 | `staff_record_relation`, `service_record` | SELECT |
| `/elder/home/summary` | GET | 老人 | `elderly`, `service_demand`, `service_record` | SELECT |
| `/elder/profile/select` | GET | 老人 | `elderly` | SELECT |
| `/elder/demand/select` | GET | 老人 | `service_demand` | SELECT |
| `/elder/record/select` | GET | 老人 | `service_record` 等 | SELECT |

## 8. 后端实现结构

```text
web      负责接口
models   负责 SQL
validate 负责参数校验
static   负责 Vue + ECharts 页面
```

当前采用 Flask-Login 管理登录状态，Flask-CORS 支持跨域请求，WTForms 校验请求参数。

## 9. 系统请求处理流程

当前项目采用前后端分离思路组织请求处理流程，整体链路如下：

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

该流程适用于查询、新增、修改、删除和统计分析接口。后续新增功能时，必须继续保持 `web -> validate -> 权限 -> models -> MySQL -> JSON -> Vue/ECharts` 的职责边界。

## 10. 当前进度

- 已连接远程 MySQL，确认数据库版本为 8.0.45。
- 已核对当前业务表与 ER 图。
- 已新增 `user_account` 认证权限表。
- 已初始化 9 个测试账号。
- 已搭建 Flask 后端基础结构。
- 已实现登录、登出、注册、修改密码、当前用户信息。
- 已实现社区管理员、机构人员、老人三类角色的首批查询接口。
- 已实现 Vue + Axios + ECharts 静态调试页面。
- 已创建并更新 `README.md` 和 `Design.md`。
- 已明确项目依赖必须安装到 `.venv` 虚拟环境，不安装到系统环境。


## 11. 后续实现计划

1. 社区管理员端补全老人、机构、人员、需求、记录的新增、修改、删除。
2. 机构人员端补全处理服务申请和录入服务记录。
3. 老人端补全修改联系方式和提交服务申请。
4. 增加统计报表接口，供 ECharts 展示需求类型分布、服务记录数量等。
5. 根据课程报告需要补充接口截图、数据库截图和测试说明。
