const { createApp } = Vue;

createApp({
  data() {
    return {
      authMode: "login",
      notice: {
        type: "",
        text: "",
      },
      dialog: {
        visible: false,
        title: "",
        message: "",
      },
      aiChat: {
        open: false,
        input: "",
        loading: false,
        lastIntent: "",
        messages: [
          {
            role: "assistant",
            text: "你好，我是 AI 智能助手。你可以直接输入自然语言，我会根据当前端口帮你处理。",
          },
        ],
      },
      aiReport: null,
      aiRecommendation: null,
      aiStaffRecommendation: null,
      aiRecordDraft: null,
      aiQueryResult: null,
      pendingAiAction: null,
      noticeTimer: null,
      loginForm: {
        role: "elder",
        username: "",
        password: "",
      },
      registerForm: {
        username: "",
        password: "",
      },
      roleName: {
        community_admin: "社区管理员",
        org: "机构",
        elder: "老人",
      },
      loginRoles: [
        { label: "社区端", value: "community_admin" },
        { label: "机构端", value: "org" },
        { label: "老人端", value: "elder" },
      ],
      currentUser: null,
      currentSummary: null,
      adminData: {
        demands: [],
        orgs: [],
        records: [],
      },
      orgData: {
        staff: [],
        records: [],
      },
      elderData: {
        profile: null,
        demands: [],
        records: [],
      },
      profileForm: {
        elderly_name: "",
        age: null,
        health_status: "",
        live_address: "",
        contact: "",
        demand_tag: "",
      },
      adminAssign: {
        demand_id: "",
        org_id: "",
      },
      adminSearch: {
        demand: "",
        org: "",
      },
      adminDemandGroups: [
        { status: "已分派", title: "已分派服务" },
        { status: "已匹配", title: "已匹配服务" },
        { status: "已完成", title: "已完成服务" },
        { status: "已评价", title: "已评价服务" },
      ],
      staffForm: {
        staff_name: "",
        qualification: "",
        available_status: "",
        contact: "",
      },
      recordStaffForm: {
        record_id: "",
        staff_ids: [],
      },
      completeForm: {
        record_id: "",
        staff_ids: [],
        service_type: "",
        service_time: "",
        service_duration: null,
      },
      demandForm: {
        demand_type: "助餐服务",
        emergency_level: "普通",
        description: "",
      },
      evaluateForm: {
        record_id: "",
        service_evaluation: "",
      },
    };
  },
  mounted() {
    axios.defaults.withCredentials = true;
  },
  computed: {
    pendingDemands() {
      return this.sortByEmergency(
        this.adminData.demands.filter((item) => this.normalizedDemandStatus(item.demand_status) === "待分派")
      );
    },
    filteredAssignableDemands() {
      const keyword = this.adminSearch.demand.trim().toLowerCase();
      const demands = this.sortByEmergency(this.adminData.demands);
      if (!keyword) {
        return demands;
      }
      return demands.filter((item) => {
        return [item.demand_id, item.elderly_name, item.demand_type, item.demand_status, this.normalizedEmergencyLevel(item.emergency_level)]
          .filter(Boolean)
          .some((value) => String(value).toLowerCase().includes(keyword));
      });
    },
    filteredOrgs() {
      const keyword = this.adminSearch.org.trim().toLowerCase();
      if (!keyword) {
        return this.adminData.orgs;
      }
      return this.adminData.orgs.filter((item) => {
        return [item.org_id, item.org_name, item.org_type]
          .filter(Boolean)
          .some((value) => String(value).toLowerCase().includes(keyword));
      });
    },
    groupedAdminDemands() {
      return this.adminDemandGroups.map((group) => ({
        ...group,
        items: this.adminData.demands.filter((item) => this.normalizedDemandStatus(item.demand_status) === group.status),
      }));
    },
    unfinishedRecords() {
      return this.orgData.records.filter((item) => this.normalizedRecordStatus(item.record_status) === "未完成");
    },
    availableStaff() {
      return this.orgData.staff.filter((item) => item.available_status === "空闲");
    },
    evaluableRecords() {
      return this.elderData.records.filter(
        (item) => this.normalizedRecordStatus(item.record_status) === "已完成"
      );
    },
    roleStats() {
      const data = this.currentSummary || {};
      if (!this.currentUser) {
        return [];
      }
      const stats = {
        community_admin: [
          { label: "老人", value: data.elder_count || 0 },
          { label: "需求", value: data.demand_count || 0 },
          { label: "高优先级待分派", value: data.urgent_pending_count || 0 },
          { label: "机构", value: data.org_count || 0 },
        ],
        org: [
          { label: "服务人员", value: data.staff_count || 0 },
          { label: "服务记录", value: data.record_count || 0 },
          { label: "紧急未完成", value: data.urgent_unfinished_count || 0 },
          { label: "已完成", value: data.finished_record_count || 0 },
        ],
        elder: [
          { label: "本人需求", value: data.demand_count || 0 },
          { label: "服务记录", value: data.record_count || 0 },
          { label: "老人编号", value: data.elderly_id || "-" },
          { label: "年龄", value: data.age || "-" },
        ],
      };
      return stats[this.currentUser.role] || [];
    },
    aiPlaceholder() {
      if (!this.currentUser) {
        return "";
      }
      const placeholders = {
        elder: "例如：我明天想找人陪我去医院复查",
        org: "例如：帮我给当前记录推荐服务人员 / 帮我整理服务记录",
        community_admin: "例如：帮我推荐需求 100 的承接机构 / 生成统计报告 / 查待分派需求",
      };
      return placeholders[this.currentUser.role] || "请输入你的问题";
    },
  },
  methods: {
    switchAuthMode(mode) {
      this.authMode = mode;
      this.clearNotice();
    },
    setNotice(text, type = "success") {
      this.notice = { text, type };
      if (this.noticeTimer) {
        clearTimeout(this.noticeTimer);
      }
      this.noticeTimer = setTimeout(() => {
        this.clearNotice();
      }, 2000);
    },
    clearNotice() {
      if (this.noticeTimer) {
        clearTimeout(this.noticeTimer);
        this.noticeTimer = null;
      }
      this.notice = { text: "", type: "" };
    },
    showDialog(title, message) {
      this.dialog = {
        visible: true,
        title,
        message,
      };
    },
    closeDialog() {
      this.dialog = {
        visible: false,
        title: "",
        message: "",
      };
    },
    toggleAiChat() {
      this.aiChat.open = !this.aiChat.open;
    },
    aiWelcomeText(role) {
      return {
        community_admin: "你好，我是社区端 AI 助手。你可以让我推荐承接机构、生成统计报告，或查询待分派需求和机构负载。",
        org: "你好，我是机构端 AI 助手。你可以让我推荐服务人员、整理服务记录草稿，或查询本机构服务记录。",
        elder: "你好，我是老人端 AI 助手。你可以描述服务需求，我会识别类型、紧急程度并回填表单。",
      }[role] || "你好，我是 AI 智能助手。你可以直接输入自然语言，我会根据当前端口帮你处理。";
    },
    resetAiChatForRole(role, keepOpen = true) {
      this.aiChat = {
        open: keepOpen ? this.aiChat.open : false,
        input: "",
        loading: false,
        lastIntent: "",
        messages: [
          {
            role: "assistant",
            text: this.aiWelcomeText(role),
          },
        ],
      };
      this.clearAiArtifacts();
    },
    clearAiChat() {
      this.aiChat.messages = [
        {
          role: "assistant",
          text: this.aiWelcomeText(this.currentUser?.role),
        },
      ];
      this.aiChat.input = "";
      this.aiChat.lastIntent = "";
      this.clearAiArtifacts();
    },
    clearAiArtifacts() {
      this.aiReport = null;
      this.aiRecommendation = null;
      this.aiStaffRecommendation = null;
      this.aiRecordDraft = null;
      this.aiQueryResult = null;
      this.pendingAiAction = null;
    },
    async login() {
      this.clearNotice();
      const loginResult = await this.request("post", "/auth/login", this.loginForm);
      if (!loginResult.success) {
        this.showDialog("登录失败", loginResult.message || "登录失败，请检查账号、密码和登录端口。");
        return;
      }
      this.currentUser = loginResult.data;
      this.resetAiChatForRole(this.currentUser.role, false);
      await this.loadRoleData();
    },
    async register() {
      this.clearNotice();
      const result = await this.request("post", "/auth/register", this.registerForm);
      if (!result.success) {
        this.showDialog("注册失败", result.message || "注册失败，请稍后重试。");
        return;
      }
      this.registerForm = {
        username: "",
        password: "",
      };
      this.loginForm.role = "elder";
      this.authMode = "login";
      this.setNotice("注册成功，请使用新账号登录。");
    },
    async logout() {
      await this.request("post", "/auth/logout", {});
      this.currentUser = null;
      this.currentSummary = null;
      this.clearRoleData();
      this.resetAiChatForRole("", false);
      this.setNotice("已退出登录。");
    },
    async loadRoleData() {
      const urls = {
        community_admin: "/admin/home/summary",
        org: "/org/home/summary",
        elder: "/elder/home/summary",
      };
      const result = await this.request("get", urls[this.currentUser.role]);
      if (result.success) {
        this.currentSummary = result.data;
      }
      if (this.currentUser.role === "community_admin") {
        this.resetAiChatForRole("community_admin");
        await this.loadAdminData();
      }
      if (this.currentUser.role === "org") {
        this.resetAiChatForRole("org");
        await this.loadOrgData();
      }
      if (this.currentUser.role === "elder") {
        this.resetAiChatForRole("elder");
        await this.loadElderData();
      }
    },
    clearRoleData() {
      this.adminData = { demands: [], orgs: [], records: [] };
      this.orgData = { staff: [], records: [] };
      this.elderData = { profile: null, demands: [], records: [] };
      this.profileForm = {
        elderly_name: "",
        age: null,
        health_status: "",
        live_address: "",
        contact: "",
        demand_tag: "",
      };
    },
    async request(method, url, data) {
      try {
        const response = await axios({ method, url, data });
        return response.data;
      } catch (error) {
        const data = error.response?.data || { success: false, message: error.message };
        this.setNotice(data.message || "请求失败，请稍后重试。", "error");
        return data;
      }
    },
    async sendAiChat() {
      const text = this.aiChat.input.trim();
      if (!text || this.aiChat.loading) {
        return;
      }
      this.aiChat.messages.push({ role: "user", text });
      this.aiChat.input = "";

      if (this.pendingAiAction) {
        if (this.isAiCancelText(text)) {
          this.cancelAiAction("已取消待执行操作。");
          return;
        }
        if (this.isAiConfirmText(text)) {
          await this.confirmAiAction();
          return;
        }
        if (this.pendingAiAction.type === "evaluate_record") {
          const revisedText = this.mergePendingActionRevision(text);
          this.cancelAiAction("已根据你的新评价重新整理。", false);
          await this.sendAiText(revisedText);
          return;
        }
        if (this.isAiRevisionText(text)) {
          const revisedText = this.mergePendingActionRevision(text);
          this.cancelAiAction("已根据你的补充重新识别，不再执行上一条待确认操作。", false);
          await this.sendAiText(revisedText);
          return;
        }
        this.aiChat.messages.push({
          role: "assistant",
          text: `我理解你可能想补充或修改上一条操作。如果要调整，请直接说新的要求，例如“改成紧急”或“我很着急”；如果要执行，请回复“确认执行”；如果不要，请回复“取消”。`,
        });
        return;
      }

      await this.sendAiText(text);
    },
    async sendAiText(text) {
      this.aiChat.loading = true;
      const payload = {
        text,
        demand_id: this.currentUser?.role === "community_admin" ? this.adminAssign.demand_id : "",
        record_id: this.currentUser?.role === "org" ? this.completeForm.record_id || this.recordStaffForm.record_id : "",
        staff_ids: this.currentUser?.role === "org"
          ? this.mergeStaffIds(this.completeForm.staff_ids, this.recordStaffForm.staff_ids)
          : [],
        last_intent: this.safeLastIntentForRole(),
      };
      const result = await this.request("post", "/ai/chat", payload);
      this.aiChat.loading = false;
      if (!result.success) {
        this.aiChat.messages.push({
          role: "assistant",
          text: this.shortAiText(result.message || "AI 助手暂时不可用。"),
        });
        return;
      }
      this.handleAiResult(result.data);
    },
    safeLastIntentForRole() {
      const allowed = {
        community_admin: ["recommend_org", "report_summary", "natural_query", "operation_help"],
        org: ["recommend_staff", "record_draft", "natural_query", "operation_help"],
        elder: ["demand_parse", "natural_query", "operation_help", "evaluate_record"],
      };
      const role = this.currentUser?.role || "";
      return (allowed[role] || []).includes(this.aiChat.lastIntent) ? this.aiChat.lastIntent : "";
    },
    async sendAiCommand(text) {
      if (this.aiChat.loading) {
        return;
      }
      this.aiChat.open = true;
      this.aiChat.input = text;
      await this.$nextTick();
      await this.sendAiChat();
    },
    async fillAiCommand(text) {
      this.aiChat.open = true;
      this.aiChat.input = text;
      await this.$nextTick();
      this.$refs.aiInput?.focus();
    },
    handleAiResult(result) {
      this.aiChat.lastIntent = result.intent || this.aiChat.lastIntent;
      this.aiChat.messages.push({
        role: "assistant",
        text: this.shortAiText(result.reply || "已完成处理。"),
      });
      if (result.intent === "demand_parse" && result.data) {
        this.demandForm = {
          demand_type: result.data.demand_type,
          emergency_level: result.data.emergency_level,
          description: result.data.description,
        };
        this.setNotice("AI 已回填服务需求表单，请确认后提交。");
        this.queueAiAction(result.pending_action);
      }
      if (result.intent === "recommend_org" && result.data) {
        this.aiRecommendation = result.data;
        this.adminAssign.org_id = result.data.recommended_org_id || this.adminAssign.org_id;
        this.setNotice("AI 已推荐机构，请确认后分派。");
        this.queueAiAction(result.pending_action);
      }
      if (result.intent === "report_summary" && result.data) {
        this.aiReport = result.data;
        this.setNotice("AI 统计报告已生成。");
      }
      if (result.intent === "natural_query" && result.data) {
        this.appendAiQuerySummary(result.data);
        this.setNotice("AI 已完成数据库查询。");
      }
      if (result.intent === "evaluate_record" && result.data) {
        this.appendEvaluationSummary(result.data);
        this.queueAiAction(result.pending_action);
      }
      if (result.intent === "recommend_staff" && result.data) {
        this.aiStaffRecommendation = result.data;
        this.recordStaffForm.staff_ids = this.mergeStaffIds(this.recordStaffForm.staff_ids, [result.data.recommended_staff_id]);
        this.recordStaffForm.record_id = result.data.record_id || this.recordStaffForm.record_id || this.completeForm.record_id;
        this.completeForm.record_id = this.recordStaffForm.record_id || this.completeForm.record_id;
        this.completeForm.staff_ids = this.mergeStaffIds(this.completeForm.staff_ids, this.recordStaffForm.staff_ids);
        this.setNotice("AI 已推荐服务人员，请确认后安排。");
        this.queueAiAction(result.pending_action);
      }
      if (result.intent === "record_draft" && result.data) {
        this.aiRecordDraft = result.data;
        this.completeForm = {
          record_id: result.data.record_id || this.completeForm.record_id,
          staff_ids: this.mergeStaffIds(this.completeForm.staff_ids, result.data.staff_ids || []),
          service_type: result.data.service_type || this.completeForm.service_type,
          service_time: result.data.service_time || this.completeForm.service_time,
          service_duration: result.data.service_duration ?? this.completeForm.service_duration,
        };
        this.setNotice("AI 已回填服务记录草稿，请确认后提交。");
        this.queueAiAction(result.pending_action);
      }
    },
    queueAiAction(action) {
      if (!action) {
        return;
      }
      this.pendingAiAction = action;
      this.aiChat.messages.push({
        role: "assistant",
        text: this.shortAiText(`我可以继续执行“${action.title}”。执行会写入数据库，请明确确认后我再操作。`),
      });
    },
    isAiConfirmText(text) {
      const normalized = text.replace(/[，。！？、,.!?\s]/g, "");
      return [
        "确认",
        "确认执行",
        "确定",
        "同意",
        "同意执行",
        "执行",
        "提交",
        "可以",
        "好的",
        "好",
        "没问题",
        "是的",
        "请执行",
        "帮我执行",
        "分派",
        "安排",
        "完成",
        "评价",
      ].includes(normalized);
    },
    isAiCancelText(text) {
      const normalized = text.replace(/[，。！？、,.!?\s]/g, "");
      return ["取消", "不要", "不执行", "先不", "算了", "停止", "撤销"].includes(normalized);
    },
    isAiRevisionText(text) {
      const revisionWords = [
        "不是",
        "不对",
        "错了",
        "改",
        "修改",
        "换成",
        "应该",
        "补充",
        "还有",
        "另外",
        "其实",
        "重新",
        "更",
        "太",
        "比较",
        "很",
        "非常",
        "特别",
        "着急",
        "急",
        "紧急",
        "马上",
        "立刻",
        "现在",
        "严重",
        "不舒服",
        "疼",
        "痛",
      ];
      return revisionWords.some((word) => text.includes(word));
    },
    mergePendingActionRevision(text) {
      if (this.pendingAiAction?.type === "create_demand") {
        const baseDescription = this.pendingAiAction.payload?.description || this.demandForm.description || "";
        return `${baseDescription}。补充说明：${text}`;
      }
      if (this.pendingAiAction?.type === "assign_demand") {
        const demandId = this.pendingAiAction.payload?.demand_id || this.adminAssign.demand_id || "";
        return `${demandId} 的承接机构需要重新推荐。补充说明：${text}`;
      }
      if (this.pendingAiAction?.type === "assign_record_staff") {
        const recordId = this.pendingAiAction.payload?.record_id || this.recordStaffForm.record_id || this.completeForm.record_id || "";
        return `为服务记录 ${recordId} 重新推荐服务人员。补充说明：${text}`;
      }
      if (this.pendingAiAction?.type === "complete_record") {
        const recordId = this.pendingAiAction.payload?.record_id || this.completeForm.record_id || "";
        return `重新整理服务记录 ${recordId}。补充说明：${text}`;
      }
      if (this.pendingAiAction?.type === "evaluate_record") {
        const recordId = this.pendingAiAction.payload?.record_id || "";
        return `重新评价服务记录 ${recordId}。补充说明：${text}`;
      }
      return text;
    },
    cancelAiAction(message = "已取消待执行操作。", appendMessage = true) {
      if (this.pendingAiAction?.action_id) {
        this.request("post", "/ai/action/cancel", { action_id: this.pendingAiAction.action_id });
      }
      this.pendingAiAction = null;
      if (appendMessage) {
        this.aiChat.messages.push({ role: "assistant", text: this.shortAiText(message) });
      }
      this.setNotice(message);
    },
    async confirmAiAction() {
      if (!this.pendingAiAction || this.aiChat.loading) {
        return;
      }

      const action = this.pendingAiAction;
      if (!action.action_id) {
        this.aiChat.messages.push({ role: "assistant", text: "当前信息不足，无法执行该操作。" });
        return;
      }

      this.aiChat.loading = true;
      const result = await this.request("post", "/ai/action/confirm", { action_id: action.action_id });
      this.aiChat.loading = false;
      if (!result.success) {
        this.aiChat.messages.push({
          role: "assistant",
          text: this.shortAiText(result.message || "执行失败，请检查表单信息后再试。"),
        });
        return;
      }

      await this.afterAiActionSuccess(action.type);
      this.pendingAiAction = null;
      this.aiChat.messages.push({
        role: "assistant",
        text: this.shortAiText(result.message || `${action.title}已完成。`),
      });
      this.setNotice(result.message || `${action.title}已完成。`);
    },
    async afterAiActionSuccess(type) {
      if (type === "create_demand") {
        this.demandForm = {
          demand_type: "助餐服务",
          emergency_level: "普通",
          description: "",
        };
        await this.loadElderData();
      }
      if (type === "assign_demand") {
        this.adminAssign = { demand_id: "", org_id: "" };
        this.aiRecommendation = null;
        await this.loadAdminData();
      }
      if (type === "assign_record_staff") {
        const recordId = this.recordStaffForm.record_id || this.completeForm.record_id;
        const staffIds = this.mergeStaffIds(this.recordStaffForm.staff_ids, this.completeForm.staff_ids);
        this.recordStaffForm = { record_id: recordId, staff_ids: staffIds };
        this.completeForm.record_id = recordId;
        this.completeForm.staff_ids = staffIds;
        this.aiStaffRecommendation = null;
        await this.loadOrgData();
      }
      if (type === "complete_record") {
        this.completeForm = {
          record_id: "",
          staff_ids: [],
          service_type: "",
          service_time: "",
          service_duration: null,
        };
        this.aiRecordDraft = null;
        await this.loadOrgData();
      }
      if (type === "evaluate_record") {
        this.evaluateForm = { record_id: "", service_evaluation: "" };
        await this.loadElderData();
      }
    },
    appendAiQuerySummary(data) {
      const rows = data.rows || [];
      if (!rows.length) {
        this.aiChat.messages.push({
          role: "assistant",
          text: this.shortAiText("没有查到符合条件的数据。"),
        });
        return;
      }
      const lines = rows.slice(0, 5).map((row, index) => {
        const id = row.record_id || row.demand_id || row.staff_id || row.org_id || row.elderly_id || `第${index + 1}条`;
        const type = row.service_type || row.demand_type || row.qualification || row.org_name || "";
        const emergency = row.emergency_level ? ` / ${this.normalizedEmergencyLevel(row.emergency_level)}` : "";
        const status = row.record_status || row.demand_status || row.available_status || "";
        const org = row.org_name ? ` / ${row.org_name}` : "";
        return `${index + 1}. ${id} ${type}${emergency}${status ? ` / ${status}` : ""}${org}`;
      });
      this.aiChat.messages.push({
        role: "assistant",
        text: `共${data.count}条：${lines.join("；")}`,
      });
    },
    appendEvaluationSummary(data) {
      if (data.record_id && data.service_evaluation) {
        this.evaluateForm = {
          record_id: data.record_id,
          service_evaluation: data.service_evaluation,
        };
        this.aiChat.messages.push({
          role: "assistant",
          text: `将${data.has_evaluation ? "修改" : "新增"}评价 ${data.record_label || data.record_id}：${data.service_evaluation}。确认后写入数据库，修改请直接说新评价，放弃请说取消。`,
        });
        return;
      }
      const records = data.pending_records || [];
      if (!records.length) {
        this.aiChat.messages.push({
          role: "assistant",
          text: "当前没有可评价的已完成服务。",
        });
        return;
      }
      const lines = records.slice(0, 5).map((row, index) => {
        const status = row.has_evaluation ? "已评价可修改" : "待评价";
        return `${index + 1}. ${row.record_id} ${row.service_type} / ${row.org_name} / ${status}`;
      });
      this.aiChat.messages.push({
        role: "assistant",
        text: `可评价服务：${lines.join("；")}。请回复“评价第1条：服务很好”，已评价的也可以这样修改。`,
      });
    },
    startDemandAi() {
      const text = this.demandForm.description.trim();
      if (text) {
        this.sendAiCommand(text);
        return;
      }
      this.aiChat.open = true;
      this.aiChat.input = "";
      this.aiChat.messages.push({
        role: "assistant",
        text: "请在这里描述你的服务需求，例如“我明天想去医院复查”，我会识别并回填表单。",
      });
    },
    async loadAdminData() {
      const demandResult = await this.request("get", "/admin/demand/select?page_size=50");
      if (demandResult.success) {
        this.adminData.demands = demandResult.data;
      }
      const orgResult = await this.request("get", "/admin/org/select?page_size=100");
      if (orgResult.success) {
        this.adminData.orgs = orgResult.data;
      }
      const recordResult = await this.request("get", "/admin/record/select?page_size=50");
      if (recordResult.success) {
        this.adminData.records = recordResult.data;
      }
      await this.loadRoleSummary();
    },
    async loadOrgData() {
      const staffResult = await this.request("get", "/org/staff/select?page_size=50");
      if (staffResult.success) {
        this.orgData.staff = staffResult.data;
      }
      const recordResult = await this.request("get", "/org/record/select?page_size=50");
      if (recordResult.success) {
        this.orgData.records = recordResult.data;
      }
      await this.loadRoleSummary();
    },
    async loadElderData() {
      const profileResult = await this.request("get", "/elder/profile/select");
      if (profileResult.success) {
        this.elderData.profile = profileResult.data;
        this.profileForm = {
          elderly_name: profileResult.data?.elderly_name || "",
          age: profileResult.data?.age ?? null,
          health_status: profileResult.data?.health_status || "",
          live_address: profileResult.data?.live_address || "",
          contact: profileResult.data?.contact || "",
          demand_tag: profileResult.data?.demand_tag || "",
        };
      }
      const demandResult = await this.request("get", "/elder/demand/select?page_size=50");
      if (demandResult.success) {
        this.elderData.demands = demandResult.data;
      }
      const recordResult = await this.request("get", "/elder/record/select?page_size=50");
      if (recordResult.success) {
        this.elderData.records = recordResult.data;
      }
      await this.loadRoleSummary();
    },
    async loadRoleSummary() {
      if (!this.currentUser) {
        return;
      }
      const urls = {
        community_admin: "/admin/home/summary",
        org: "/org/home/summary",
        elder: "/elder/home/summary",
      };
      const result = await this.request("get", urls[this.currentUser.role]);
      if (result.success) {
        this.currentSummary = result.data;
      }
    },
    statusClass(status) {
      status = this.normalizedStatus(status);
      return {
        待分派: "tag-wait",
        已分派: "tag-assigned",
        已匹配: "tag-matched",
        已完成: "tag-finished",
        已评价: "tag-rated",
        未完成: "tag-wait",
        空闲: "tag-free",
        忙碌: "tag-busy",
        休假: "tag-leave",
      }[status] || "";
    },
    emergencyClass(level) {
      level = this.normalizedEmergencyLevel(level);
      return {
        紧急: "tag-emergency-high",
        较急: "tag-emergency-medium",
        普通: "tag-emergency-normal",
      }[level] || "tag-emergency-normal";
    },
    emergencyRank(level) {
      return { 紧急: 0, 较急: 1, 普通: 2 }[level] ?? 3;
    },
    normalizedEmergencyLevel(level) {
      return ["紧急", "较急", "普通"].includes(level) ? level : "";
    },
    sortByEmergency(rows) {
      return [...rows].sort((a, b) => {
        const rankDiff = this.emergencyRank(a.emergency_level) - this.emergencyRank(b.emergency_level);
        if (rankDiff !== 0) {
          return rankDiff;
        }
        return String(a.submit_time || "").localeCompare(String(b.submit_time || ""));
      });
    },
    normalizedRecordStatus(status) {
      return status || "未完成";
    },
    normalizedDemandStatus(status) {
      return status || "";
    },
    normalizedStatus(status) {
      return this.normalizedDemandStatus(this.normalizedRecordStatus(status));
    },
    shortAiText(text, maxLength = 90) {
      const value = String(text || "").replace(/\s+/g, " ").trim();
      if (value.length <= maxLength) {
        return value;
      }
      return `${value.slice(0, maxLength).replace(/[，。；、\s]+$/, "")}...`;
    },
    fieldLabel(key) {
      return {
        demand_id: "需求编号",
        demand_type: "需求类型",
        demand_status: "需求状态",
        emergency_level: "紧急程度",
        description: "需求描述",
        submit_time: "提交时间",
        elderly_id: "老人编号",
        elderly_name: "老人姓名",
        age: "年龄",
        health_status: "健康状态",
        live_address: "居住地址",
        contact: "联系方式",
        demand_tag: "需求标签",
        record_id: "记录编号",
        record_status: "记录状态",
        service_type: "服务类型",
        service_time: "服务时间",
        service_duration: "服务时长",
        service_evaluation: "服务评价",
        org_id: "机构编号",
        org_name: "机构名称",
        org_type: "机构类型",
        staff_id: "人员编号",
        staff_name: "人员姓名",
        staff_names: "服务人员",
        qualification: "资质",
        available_status: "人员状态",
        record_count: "记录数",
        unfinished_count: "未完成数",
        finished_count: "已完成数",
      }[key] || key;
    },
    selectAdminDemand(demandId) {
      this.adminAssign.demand_id = demandId;
      this.setNotice("已选择服务需求，可为它生成或追加服务过程记录。");
    },
    selectOrgRecord(recordId) {
      this.syncSelectedOrgRecord(recordId);
      this.setNotice("已选择服务记录。");
    },
    syncSelectedOrgRecord(recordId) {
      this.recordStaffForm.record_id = recordId;
      this.completeForm.record_id = recordId;
      const record = this.orgData.records.find((item) => item.record_id === recordId);
      if (!record) {
        return;
      }
      const staffIds = this.staffIdsForRecord(record);
      this.recordStaffForm.staff_ids = staffIds;
      this.completeForm.staff_ids = staffIds;
    },
    staffIdsForRecord(record) {
      const ids = String(record?.staff_ids || "").split("、").map((id) => id.trim()).filter(Boolean);
      if (ids.length) {
        return ids.filter((id) => this.orgData.staff.some((staff) => staff.staff_id === id));
      }
      const names = String(record?.staff_names || "").split("、").map((name) => name.trim()).filter(Boolean);
      return this.orgData.staff.filter((staff) => names.includes(staff.staff_name)).map((staff) => staff.staff_id);
    },
    mergeStaffIds(currentIds, newIds) {
      const values = [...(currentIds || []), ...(newIds || [])].filter(Boolean).map((id) => String(id));
      return [...new Set(values)];
    },
    toggleStaffSelection(formName, staffId) {
      // 服务记录与服务人员是 M:N，这里用数组维护当前记录选中的多名人员。
      const form = this[formName];
      if (!form) {
        return;
      }
      const id = String(staffId);
      const ids = (form.staff_ids || []).map((item) => String(item));
      form.staff_ids = ids.includes(id) ? ids.filter((item) => item !== id) : [...ids, id];
    },
    isStaffSelected(formName, staffId) {
      const form = this[formName];
      return Boolean(form && (form.staff_ids || []).map((item) => String(item)).includes(String(staffId)));
    },
    recordHasAssignedStaff(recordId) {
      const record = this.orgData.records.find((item) => item.record_id === recordId);
      return Boolean(record?.staff_ids || record?.staff_names);
    },
    ensureSelectedOrgRecord(actionName) {
      const recordId = this.completeForm.record_id || this.recordStaffForm.record_id;
      if (recordId) {
        this.syncSelectedOrgRecord(recordId);
        return true;
      }
      this.showDialog("请先选择用户", `请先在服务记录列表中选择待服务老人，选择后方能${actionName}。`);
      return false;
    },
    async requestAiStaffRecommendation() {
      if (!this.ensureSelectedOrgRecord("匹配服务人员")) {
        return;
      }
      await this.sendAiCommand("推荐当前服务记录的服务人员");
    },
    async requestAiRecordDraft() {
      if (!this.ensureSelectedOrgRecord("整理服务记录")) {
        return;
      }
      await this.sendAiCommand("整理服务记录草稿");
    },
    async assignDemand() {
      const result = await this.request("post", "/admin/demand/assign", this.adminAssign);
      if (result.success) {
        this.adminAssign = { demand_id: "", org_id: "" };
        await this.loadAdminData();
        this.setNotice(result.message || "服务过程记录已生成。");
      }
    },
    async updateProfile() {
      const result = await this.request("post", "/elder/profile/update", this.profileForm);
      if (result.success) {
        this.currentUser.display_name = this.profileForm.elderly_name;
        await this.loadElderData();
        this.setNotice(result.message || "个人资料已保存。");
      }
    },
    async createStaff() {
      const result = await this.request("post", "/org/staff/create", this.staffForm);
      if (result.success) {
        this.staffForm = {
          staff_name: "",
          qualification: "",
          available_status: "",
          contact: "",
        };
        await this.loadOrgData();
        this.setNotice(result.message || "服务人员新增成功。");
      }
    },
    async assignRecordStaff() {
      if (!this.recordStaffForm.record_id) {
        this.showDialog("请先选择用户", "请先选择待服务老人，选择后方能安排服务人员。");
        return;
      }
      if (!this.recordStaffForm.staff_ids.length) {
        this.showDialog("请先选择服务人员", "请至少选择一名空闲服务人员后再安排。");
        return;
      }
      const result = await this.request("post", "/org/record/staff/assign", this.recordStaffForm);
      if (result.success) {
        const recordId = this.recordStaffForm.record_id;
        const staffIds = [...this.recordStaffForm.staff_ids];
        this.completeForm.record_id = recordId;
        this.completeForm.staff_ids = staffIds;
        await this.loadOrgData();
        this.setNotice(result.message || "服务人员安排成功。");
      }
    },
    async completeRecord() {
      if (!this.completeForm.record_id) {
        this.showDialog("请先选择用户", "请先选择待服务老人，选择后方能完成服务记录。");
        return;
      }
      if (!this.completeForm.staff_ids.length && !this.recordHasAssignedStaff(this.completeForm.record_id)) {
        this.showDialog("请先选择服务人员", "服务记录标记为已完成前，必须至少安排一名服务人员。");
        return;
      }
      const result = await this.request("post", "/org/record/complete", this.completeForm);
      if (result.success) {
        this.completeForm = {
          record_id: "",
          staff_ids: [],
          service_type: "",
          service_time: "",
          service_duration: null,
        };
        await this.loadOrgData();
        this.setNotice(result.message || "服务记录已完成。");
      }
    },
    async createDemand() {
      const result = await this.request("post", "/elder/demand/create", this.demandForm);
      if (result.success) {
        this.demandForm = {
          demand_type: "助餐服务",
          emergency_level: "普通",
          description: "",
        };
        await this.loadElderData();
        this.setNotice(result.message || "服务需求提交成功。");
      }
    },
    async evaluateRecord() {
      const result = await this.request("post", "/elder/record/evaluate", this.evaluateForm);
      if (result.success) {
        this.evaluateForm = { record_id: "", service_evaluation: "" };
        await this.loadElderData();
        this.setNotice(result.message || "服务评价已保存。");
      }
    },
    syncEvaluationText() {
      // 选择已评价记录时自动带出现有评价，老人可直接在原文上修改。
      const record = this.elderData.records.find((item) => item.record_id === this.evaluateForm.record_id);
      this.evaluateForm.service_evaluation = record?.service_evaluation || "";
    },
  },
}).mount("#app");
