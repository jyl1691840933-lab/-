/**
 * 豆包AI API 本地代理服务器
 * 用于前端 file:// 页面调用豆包API，避免跨域和API Key暴露
 *
 * 启动方式：
 *   1. 设置环境变量：set ARK_API_KEY=你的APIKey
 *   2. 运行：node server.js
 *   3. 浏览器访问 index.html 即可
 *
 * API Key 获取：https://console.volcengine.com/ark/region:ark+cn-beijing/apikey
 */

const http = require("http");

const PORT = 3001;
const ARK_API_KEY = process.env.ARK_API_KEY || "";
const ARK_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3/chat/completions";
const MODEL = process.env.ARK_MODEL || "doubao-seed-2-1-pro-260628";

const SYSTEM_PROMPT = `你是一个3D打印模型创意助手。用户会输入模型关键词，你需要分析并返回结构化JSON。

严格按照以下JSON格式返回，不要输出任何其他文字：
{
  "source": "用户原始输入",
  "style": "风格描述，如未来潮玩角色、硬表面机械、东方潮玩生物、参数化产品设计等",
  "structure": "结构要点，如头身比例强化+底座分件、外壳分件+关节留缝等",
  "fabrication": "打印制造建议，如树脂高精度打印、PLA/FDM原型等",
  "scale": "推荐比例，如1:8、1:10、桌面、按尺寸等",
  "forms": [
    ["方案A中文名称", "英文短描述", "宽度百分比", "高度百分比", "细节宽度百分比", "细节Y位置百分比"],
    ["方案B中文名称", "英文短描述", "宽度百分比", "高度百分比", "细节宽度百分比", "细节Y位置百分比"],
    ["方案C中文名称", "英文短描述", "宽度百分比", "高度百分比", "细节宽度百分比", "细节Y位置百分比"]
  ]
}

要求：
- forms必须恰好3套方案
- 百分比是20-80之间的数字，带%号，如"34%"
- 三套方案的数值要有明显差异，体现不同造型
- 根据用户输入的角色/产品类型，给出贴切的风格和方案名称
- 只返回JSON，不要markdown代码块，不要解释`;

function parseJsonSafe(text) {
  try {
    return JSON.parse(text);
  } catch (e) {
    const match = text.match(/\{[\s\S]*\}/);
    if (match) {
      try {
        return JSON.parse(match[0]);
      } catch (e2) {
        return null;
      }
    }
    return null;
  }
}

function callDoubao(prompt) {
  return new Promise((resolve, reject) => {
    const body = JSON.stringify({
      model: MODEL,
      messages: [
        { role: "system", content: SYSTEM_PROMPT },
        { role: "user", content: prompt }
      ],
      temperature: 0.8,
      max_tokens: 1024
    });

    const url = new URL(ARK_BASE_URL);
    const options = {
      hostname: url.hostname,
      port: url.port || 443,
      path: url.pathname,
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${ARK_API_KEY}`,
        "Content-Length": Buffer.byteLength(body)
      }
    };

    const https = require("https");
    const req = https.request(options, (res) => {
      let data = "";
      res.on("data", (chunk) => { data += chunk; });
      res.on("end", () => {
        try {
          const result = JSON.parse(data);
          if (result.error) {
            reject(new Error(result.error.message || "API返回错误"));
            return;
          }
          const content = result.choices?.[0]?.message?.content || "";
          const parsed = parseJsonSafe(content);
          if (parsed) {
            resolve(parsed);
          } else {
            reject(new Error("AI返回内容无法解析为JSON"));
          }
        } catch (e) {
          reject(new Error("解析API响应失败: " + e.message));
        }
      });
    });

    req.on("error", (e) => {
      reject(new Error("请求豆包API失败: " + e.message));
    });

    req.write(body);
    req.end();
  });
}

const server = http.createServer(async (req, res) => {
  // CORS 头，允许 file:// 来源
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type");

  if (req.method === "OPTIONS") {
    res.writeHead(204);
    res.end();
    return;
  }

  if (req.method === "GET" && req.url === "/") {
    res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
    res.end(`
      <h2>豆包AI代理服务器运行中</h2>
      <p>端口: ${PORT}</p>
      <p>模型: ${MODEL}</p>
      <p>API Key: ${ARK_API_KEY ? "已配置" : "未配置（请设置环境变量 ARK_API_KEY）"}</p>
      <p>POST /api/generate  Body: {"prompt": "你的描述"}</p>
    `);
    return;
  }

  if (req.method === "POST" && req.url === "/api/generate") {
    let body = "";
    req.on("data", (chunk) => { body += chunk; });
    req.on("end", async () => {
      try {
        const { prompt } = JSON.parse(body);
        if (!prompt || !prompt.trim()) {
          res.writeHead(400, { "Content-Type": "application/json" });
          res.end(JSON.stringify({ error: "prompt不能为空" }));
          return;
        }

        if (!ARK_API_KEY) {
          res.writeHead(500, { "Content-Type": "application/json" });
          res.end(JSON.stringify({ error: "服务器未配置ARK_API_KEY环境变量" }));
          return;
        }

        console.log(`[${new Date().toLocaleTimeString()}] 收到请求: ${prompt.slice(0, 50)}`);
        const result = await callDoubao(prompt);
        console.log(`[${new Date().toLocaleTimeString()}] AI返回成功`);

        res.writeHead(200, { "Content-Type": "application/json; charset=utf-8" });
        res.end(JSON.stringify(result));
      } catch (e) {
        console.error(`[${new Date().toLocaleTimeString()}] 错误: ${e.message}`);
        res.writeHead(500, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ error: e.message }));
      }
    });
    return;
  }

  res.writeHead(404, { "Content-Type": "application/json" });
  res.end(JSON.stringify({ error: "Not Found" }));
});

server.listen(PORT, () => {
  console.log("========================================");
  console.log("  豆包AI代理服务器已启动");
  console.log("  地址: http://localhost:" + PORT);
  console.log("  模型: " + MODEL);
  console.log("  API Key: " + (ARK_API_KEY ? "已配置" : "未配置！"));
  console.log("========================================");
  if (!ARK_API_KEY) {
    console.log("");
    console.log("提示：请先设置API Key再使用：");
    console.log("  set ARK_API_KEY=你的APIKey");
    console.log("  node server.js");
    console.log("");
    console.log("获取地址：https://console.volcengine.com/ark/region:ark+cn-beijing/apikey");
  }
});
