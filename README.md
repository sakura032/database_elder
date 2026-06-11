# 居民社区养老服务需求分析与智能匹配系统

## 1. 项目名称

居民社区养老服务需求分析与智能匹配系统。

## 2. 项目简介

本项目围绕老年人、服务需求、服务记录、服务人员、服务机构、社区六个核心实体，实现社区养老服务需求管理、服务执行记录管理和多角色权限访问。

项目当前阶段重点是完成后端代码结构、认证权限、测试账号、基础查询接口，以及 Vue + ECharts 前端调试页面。

## 3. 默认测试账号

测试数据所有默认测试账号初始密码均为：

```text
123456
```

| 角色 | 用户名 | 绑定对象 |
|---|---|---|
| 社区管理员 | `admin01` | 社区 `1` |
| 社区管理员 | `admin02` | 社区 `2` |
| 社区管理员 | `admin03` | 社区 `3` |
| 机构人员 | `staff001` | 服务人员 `001` |
| 机构人员 | `staff002` | 服务人员 `002` |
| 机构人员 | `staff003` | 服务人员 `003` |
| 老人 | `elderE1` | 老人 `E1` |
| 老人 | `elderE2` | 老人 `E2` |
| 老人 | `elderE3` | 老人 `E3` |

## 4. 项目功能

系统按角色划分为老人、机构人员、社区管理员三类用户。

公共功能：

- 登录
- 登出
- 注册
- 修改密码
- 查看当前用户信息

老人功能：

- 查看个人基本信息
- 修改个人联系方式
- 提交服务申请
- 查看个人服务申请
- 查看个人服务记录
- 查看健康档案或关怀记录

机构人员功能：

- 查看所属机构信息
- 查看老人服务申请
- 处理服务申请
- 录入服务记录
- 查看本机构服务统计

社区管理员功能：

- 管理老人信息
- 管理机构信息
- 管理机构人员信息
- 管理服务申请与服务记录
- 查看系统统计报表

说明：当前不新增“社区服务项目”表，功能范围严格围绕现有 ER 图和当前数据库表。

## 5. 技术栈

| 类型 | 技术 |
|---|---|
| 后端 | Python + Flask |
| 数据库 | MySQL |
| 数据库连接 | PyMySQL |
| 参数校验 | WTForms |
| 登录状态管理 | Flask-Login |
| 跨域支持 | Flask-CORS |
| 前端 | Vue |
| 图表展示 | ECharts |
| 前端请求 | Axios |

## 6. 目录结构

```text
database_elder/
  app/                         # Flask 后端主应用目录
    __init__.py                # 创建 Flask 应用，注册蓝图，初始化 Flask-Login 和跨域配置
    config.py                  # 项目配置文件，保存数据库连接、Session 等配置
    db.py                      # 数据库连接工具，统一创建 PyMySQL 连接和游标
    web/                       # 接口层，负责接收请求、检查登录状态和角色权限
      session.py               # 公共认证接口：登录、登出、注册、修改密码、当前用户信息
      admin.py                 # 社区管理员接口：老人、机构、人员、需求、记录查询
      staff.py                 # 机构人员接口：所属机构、待处理需求、本人服务记录查询
      elder.py                 # 老人接口：个人信息、个人需求、个人服务记录查询
      auth_guard.py            # 登录校验和角色权限校验装饰器
    models/                    # 数据访问层，负责写 SQL 字符串并通过 PyMySQL 执行
      session.py               # 账号表 user_account 相关 SQL
      admin.py                 # 社区管理员相关 SQL
      staff.py                 # 机构人员相关 SQL
      elder.py                 # 老人相关 SQL
    validate/                  # 参数校验层，使用 WTForms 校验请求参数是否合法
      session.py               # 登录、注册、修改密码参数校验
      admin.py                 # 社区管理员查询参数校验
      staff.py                 # 机构人员查询参数校验
      elder.py                 # 老人查询参数校验
    static/                    # 前端静态资源目录
      index.html               # Vue 页面入口
      main.js                  # Vue、Axios、ECharts 前端逻辑
      style.css                # 页面样式
  Design.md                    # 项目设计文档，记录设计依据、接口、进度和处理流程
  README.md                    # 项目说明文档，记录功能、结构、运行方式和注意事项
  requirements.txt             # Python 依赖列表，只安装到项目虚拟环境
  run.py                       # 项目启动入口
```

## 7. 后端结构

后端采用三层拆分：

| 目录 | 职责 |
|---|---|
| `web/` | 负责接口路由、登录状态、角色权限 |
| `models/` | 直接使用 PyMySQL 写 SQL 字符串并访问数据库 |
| `validate/` | 使用 WTForms 校验请求参数是否合法 |
| `static/` | 放置 Vue、Axios、ECharts 前端页面 |

文件对应关系：

| web | models | validate |
|---|---|---|
| `session.py` | `session.py` | `session.py` |
| `admin.py` | `admin.py` | `admin.py` |
| `staff.py` | `staff.py` | `staff.py` |
| `elder.py` | `elder.py` | `elder.py` |

## 8. 数据库设计

远程数据库信息：

```text
数据库类型：MySQL
主机：10.160.70.167
端口：3306
数据库：pension_service
用户名：root
密码：root
MySQL 版本：8.0.45
```

核心业务表：

| 表名 | 对应实体 |
|---|---|
| `elderly` | 老年人 |
| `service_demand` | 服务需求 |
| `service_record` | 服务记录 |
| `service_staff` | 服务人员 |
| `service_org` | 服务机构 |
| `community` | 社区 |
| `staff_record_relation` | 服务人员执行服务记录的多对多中间表 |
| `user_account` | 登录账号与角色权限表 |

## 9. 编号规则

当前数据库已有编号规则：

| 对象 | 示例 | 说明 |
|---|---|---|
| 老人 | `E1` | `elderly.elderly_id` |
| 服务需求 | `D1` | `service_demand.demand_id` |
| 服务记录 | `R1` | `service_record.record_id` |
| 服务人员 | `001` | `service_staff.staff_id` |
| 服务机构 | `01` | `service_org.org_id` |
| 社区 | `1` | `community.community_id` |

后续新增数据时应沿用现有编号风格，避免混用中文编号或随机 UUID。

## 10. 环境要求

- Python 3.10 或更高版本
- MySQL 可访问远程数据库 `10.160.70.167:3306`
- 本机可安装 Python 依赖

注意：依赖必须安装到项目虚拟环境 `.venv` 中，不要安装到系统 Python 或 Anaconda 环境。

## 11. 本地运行

### 1. 创建并激活虚拟环境

Windows PowerShell：

```powershell
py -3.10 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 2. 安装依赖

```powershell
pip install -r requirements.txt
```

### 3. 准备数据库

远程数据库已经准备好，目标数据库为 `pension_service`，当前核心业务表包括：

```text
community
elderly
service_demand
service_org
service_staff
service_record
staff_record_relation
user_account
```

其中 `user_account` 是本项目新增的认证权限表，默认测试账号已经初始化。

### 4. 配置数据库连接

默认数据库配置位于 `app/config.py`：

```text
DB_HOST = 10.160.70.167
DB_PORT = 3306
DB_USER = root
DB_PASSWORD = root
DB_NAME = pension_service
```

如需临时覆盖配置，可以在 PowerShell 中设置环境变量：

```powershell
$env:DB_HOST="10.160.70.167"
$env:DB_PORT="3306"
$env:DB_USER="root"
$env:DB_PASSWORD="root"
$env:DB_NAME="pension_service"
```

### 5. 启动项目

```powershell
python run.py
```

访问：

```text
http://127.0.0.1:5000/
```

## 12. 前端运行

当前前端放在 Flask 的 `app/static/` 目录中，不需要单独启动 Vue 开发服务器。

启动 Flask 后直接访问：

```text
http://127.0.0.1:5000/
```

页面使用 Vue 管理状态，Axios 请求后端接口，ECharts 展示不同角色的统计结果。

## 13. 推荐学习/阅读顺序

1. 阅读 `Design.md`，理解 ER 图、数据库现状和当前进度。
2. 阅读 `README.md`，理解项目结构和运行方式。
3. 查看 `app/config.py` 和 `app/db.py`，理解数据库连接。
4. 查看 `app/web/session.py`，理解登录、注册、修改密码。
5. 查看 `app/web/admin.py`、`app/web/staff.py`、`app/web/elder.py`，理解三类角色接口。
6. 查看 `app/models/` 下同名文件，理解每个接口对应的 SQL。
7. 查看 `app/validate/` 下同名文件，理解 WTForms 参数校验。
8. 查看 `app/static/`，理解前端如何调用接口并渲染图表。

## 14. 注意事项

- 公共注册只允许老人账号，社区管理员和机构人员账号由管理员预置或后续管理员端创建。
- 接口命名遵循 `/角色/对象/动作`，例如 `/admin/elder/select`。
- 认证公共接口统一放在 `/auth/...`。
- 后续新增接口时，应同步更新 `Design.md` 和本文件。
