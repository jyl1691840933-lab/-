# 豆包AI API 接入使用说明

## 已完成的修改

### 1. 后端代理服务器 (`server.js`)
- 监听端口：`http://localhost:3001`
- 接口：`POST /api/generate`，接收 `{"prompt": "用户输入"}`
- 转发请求到豆包API（火山引擎方舟），避免前端跨域和API Key暴露
- API调用失败时自动回退到本地模拟

### 2. 前端修改 (`index.html`)
- `runGenerationAnalysis` 函数改为异步，调用本地代理API
- AI返回结构化JSON（风格/结构/比例/3套方案），完全替换原有的正则模拟
- 思考动画与API请求并行，保证至少1.5秒动画时间
- API不可用时自动回退到本地 `getPromptProfile` 模拟

## 使用步骤

### 第一步：获取豆包API Key
1. 访问 https://console.volcengine.com/ark/region:ark+cn-beijing/apikey
2. 注册/登录火山引擎账号
3. 开通豆包大模型服务（推荐 `doubao-seed-2-1-pro-260628`）
4. 创建API Key并复制

### 第二步：启动后端服务器
打开命令行（CMD或PowerShell），执行：

```cmd
cd /d D:\AI_project\web_project\--main
set ARK_API_KEY=你的APIKey
node server.js
```

看到以下输出表示启动成功：
```
========================================
  豆包AI代理服务器已启动
  地址: http://localhost:3001
  模型: doubao-seed-2-1-pro-260628
  API Key: 已配置
========================================
```

### 第三步：使用网站
1. 保持服务器窗口运行（不要关闭）
2. 浏览器打开 `index.html`
3. 进入"创作工作室" → "AI协作生成"
4. 输入模型关键词，点击发送
5. AI会真实分析你的输入并返回3套三视图方案

## 注意事项

- **服务器必须保持运行**：关闭命令行窗口后API调用会失败，但网站会自动回退到本地模拟
- **API Key不要提交到代码仓库**：通过环境变量传入，不写在代码里
- **模型可更换**：设置环境变量 `set ARK_MODEL=其他模型ID` 可切换模型
- **费用**：豆包API按token计费，具体价格参考火山引擎官网
- **本地模拟回退**：如果服务器没启动或API调用失败，控制台会打印警告，网站仍能用预设模板正常运行

## 文件清单

| 文件 | 说明 |
|------|------|
| `index.html` | 网站主文件（已修改AI协作生成逻辑） |
| `server.js` | 新增的Node.js后端代理服务器 |
| `AI接入说明.md` | 本说明文档 |

## 常见问题

**Q: 提示"API失败，使用本地模拟"怎么办？**
A: 检查服务器是否启动、API Key是否正确、网络是否能访问火山引擎。

**Q: 可以不用后端直接在前端调用吗？**
A: 技术上可以，但会暴露API Key且有跨域限制，不推荐。

**Q: 想换其他AI服务商？**
A: 修改 `server.js` 中的 `ARK_BASE_URL` 和请求格式即可，前端不用改。
