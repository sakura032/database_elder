const { createApp, nextTick } = Vue;

createApp({
  data() {
    return {
      loginForm: {
        username: "admin01",
        password: "123456",
      },
      quickUsers: [
        { label: "管理员", username: "admin01" },
        { label: "机构人员", username: "staff001" },
        { label: "老人", username: "elderE1" },
      ],
      roleName: {
        admin: "社区管理员",
        staff: "机构人员",
        elder: "老人",
      },
      currentUser: null,
      output: "等待登录...",
      chart: null,
    };
  },
  mounted() {
    axios.defaults.withCredentials = true;
    this.chart = echarts.init(document.getElementById("chart"));
    this.renderChart("未登录", []);
  },
  methods: {
    useAccount(username) {
      this.loginForm.username = username;
      this.loginForm.password = "123456";
    },
    async login() {
      const loginResult = await this.request("post", "/auth/login", this.loginForm);
      if (!loginResult.success) {
        return;
      }
      this.currentUser = loginResult.data;
      await this.loadRoleData();
    },
    async logout() {
      await this.request("post", "/auth/logout", {});
      this.currentUser = null;
      this.renderChart("未登录", []);
    },
    async loadRoleData() {
      const urls = {
        admin: "/admin/home/summary",
        staff: "/staff/home/summary",
        elder: "/elder/home/summary",
      };
      const result = await this.request("get", urls[this.currentUser.role]);
      if (result.success) {
        this.renderRoleChart(this.currentUser.role, result.data);
      }
    },
    async request(method, url, data) {
      try {
        const response = await axios({ method, url, data });
        this.output = JSON.stringify(response.data, null, 2);
        return response.data;
      } catch (error) {
        const data = error.response?.data || { success: false, message: error.message };
        this.output = JSON.stringify(data, null, 2);
        return data;
      }
    },
    renderRoleChart(role, data) {
      const chartData = {
        admin: [
          ["老人", data.elder_count],
          ["需求", data.demand_count],
          ["记录", data.record_count],
          ["人员", data.staff_count],
          ["机构", data.org_count],
          ["社区", data.community_count],
        ],
        staff: [
          ["本人服务记录", data.record_count],
        ],
        elder: [
          ["本人需求", data.demand_count],
          ["本人服务记录", data.record_count],
        ],
      }[role];
      this.renderChart(this.roleName[role], chartData);
    },
    renderChart(title, data) {
      nextTick(() => {
        this.chart.setOption({
          title: { text: title, left: 8, top: 8, textStyle: { fontSize: 16 } },
          tooltip: {},
          grid: { left: 44, right: 20, top: 56, bottom: 32 },
          xAxis: { type: "category", data: data.map((item) => item[0]) },
          yAxis: { type: "value", minInterval: 1 },
          series: [
            {
              type: "bar",
              data: data.map((item) => item[1]),
              itemStyle: { color: "#317454" },
            },
          ],
        });
      });
    },
  },
}).mount("#app");
