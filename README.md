# AstrBot 插件：服务器状态卡片

一个为 AstrBot 设计的、美观实用的服务器状态监控插件。它可以生成具有**二次元毛玻璃风格**的可视化状态卡片，支持实时监控、AI智能分析和高度自定义。

## ✨ 核心特性

- **🎨 精美可视化**：圆角白色半透明毛玻璃效果，支持自定义背景、字体和二次元角色装饰。
- **🤖 AI智能分析**：集成大语言模型，自动分析服务器状态并提供优化建议（需配置LLM提供商）。
- **📊 全面监控**：实时监控CPU、内存、磁盘使用率、温度及多服务器连接状态。
- **⚙️ 高度可配置**：所有样式、触发命令、监控项均可通过WebUI界面轻松配置。
- **🔄 自动更新**：支持定时自动刷新状态，减少手动操作。

## 📦 安装方法

### 方式一：通过AstrBot插件市场安装（推荐）
1. 在AstrBot WebUI中打开「插件市场」
2. 搜索「服务器状态卡片」
3. 点击安装并启用

### 方式二：手动安装
1. 下载插件压缩包或克隆仓库
2. 将插件文件夹解压到 `AstrBot/data/plugins/` 目录下
3. 重启AstrBot或在WebUI中重载插件

## ⚙️ 配置说明

### 基础配置
| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `trigger_commands` | 触发命令（多个用逗号分隔） | `/status,/服务器状态` |
| `enable_ai_analysis` | 是否启用AI智能分析 | `true` |
| `card_background` | 卡片背景图片URL | 空（纯色背景） |

### 视觉样式
| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `font_path` | 自定义字体文件（放在fonts目录） | 空（使用系统字体） |
| `blur_strength` | 毛玻璃效果强度(1-20) | `10` |
| `card_opacity` | 卡片透明度(0.1-1) | `0.85` |
| `border_radius` | 圆角大小(0-50) | `20` |
| `show_anime_character` | 显示二次元角色装饰 | `true` |

### 服务器监控
| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `monitored_servers` | 监控的服务器列表（JSON格式） | `{"本地API": "127.0.0.1:8080"}` |
| `update_interval` | 自动更新间隔（分钟，0为禁用） | `5` |
| `ping_timeout` | 服务器检测超时时间（秒） | `3` |

### AI分析配置
| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `ai_analysis_prompt` | AI分析提示词模板 | [见下方模板] |
| `enable_detailed_logs` | 启用详细日志（调试用） | `false` |

## 🚀 使用方法

### 基础命令
```
/status                    # 查看完整的服务器状态卡片
/服务器状态               # 使用中文命令查看状态
/status help              # 查看帮助信息
```

### 功能示例
1. **查看状态**：发送 `/status` 获取当前服务器状态卡片
2. **监控指定服务器**：在配置中添加 `{"我的网站": "example.com:443"}`
3. **自定义样式**：上传背景图片和字体文件，调整颜色方案
4. **AI分析**：启用AI分析后，卡片会包含智能评估和建议

## 🎨 自定义样式

### 字体推荐
1. **标题字体**：优设标题黑、得意黑（SmileySans）
2. **正文字体**：思源黑体、阿里巴巴普惠体
3. **下载来源**：[猫啃网](https://www.maoken.com/)（免费可商用字体）

### 背景建议
- **二次元风格**：使用低饱和度的动漫背景图
- **渐变背景**：CSS渐变生成器创建柔和背景
- **本地图片**：将图片放入插件目录后使用相对路径

### 颜色方案
默认采用紫色系主题，可在配置中修改：
```json
{
  "primary": "#8a2be2",    // 主色调
  "secondary": "#9370db",  // 辅助色
  "success": "#32cd32",    // 成功/正常
  "warning": "#ffa500",    // 警告
  "error": "#ff4500"       // 错误
}
```

## 🔧 开发与调试

### 项目结构
```
astrbot_plugin_server_status/
├── main.py                 # 主插件代码
├── metadata.yaml           # 插件元数据
├── _conf_schema.json       # 配置定义
├── requirements.txt        # Python依赖
├── README.md              # 说明文档
├── fonts/                  # 字体目录（可选）
│   └── *.ttf              # 字体文件
└── templates/             # HTML模板目录
    └── status_card.html   # 状态卡片模板
```

### 依赖说明
```txt
aiohttp>=3.8.0      # 异步HTTP客户端
psutil>=5.9.0       # 系统信息获取
pythonping>=1.1.0   # 服务器连通性测试
pillow>=10.0.0      # 图像处理
jinja2>=3.0.0       # 模板渲染
fonttools>=4.0.0    # 字体处理
```

### 常见问题

#### Q1: 插件加载失败，显示导入错误
**A**: 确保使用正确的导入语句：
```python
# 正确方式
import astrbot.api.message_components as Comp
# 错误方式（可能导致导入失败）
from astrbot.api.message_components import Comp
```

#### Q2: AI分析功能不可用
**A**: 
1. 确认已在AstrBot中配置LLM提供商
2. 检查 `enable_ai_analysis` 配置为 `true`
3. 查看日志确认是否有API调用错误

#### Q3: 图片渲染异常
**A**:
1. 检查背景图片URL是否可访问
2. 确认Pillow库已正确安装
3. 查看系统是否有足够内存进行图片处理

#### Q4: 服务器监控不准确
**A**:
1. 检查服务器地址格式是否正确（IP:端口）
2. 调整 `ping_timeout` 配置以适应网络环境
3. 确认防火墙未阻止ICMP/TCP检测

## 📝 AI分析提示词模板

```text
请分析以下服务器状态数据，给出简洁明了的分析结果和优化建议：

{status_data}

请用中文回答，包含以下内容：
1. 整体状态评估（使用表情符号）
2. 潜在问题分析
3. 优化建议
4. 安全提醒（如果需要）

语气友好，适合普通用户理解。
```

## 🔄 更新日志

### v1.0.0 (2024-XX-XX)
- 🎉 初始版本发布
- ✨ 基础服务器状态监控功能
- 🤖 集成AI智能分析
- 🎨 可自定义的毛玻璃风格卡片
- ⚙️ 完整的WebUI配置支持

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 🤝 贡献指南

欢迎提交Issue和Pull Request！

1. Fork 本仓库
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启一个 Pull Request

## 📞 支持与反馈

- GitHub Issues: [提交问题或建议](https://github.com/yourname/astrbot_plugin_server_status/issues)
- AstrBot社区: [官方QQ群](https://docs.astrbot.org/community)
- 文档: [AstrBot插件开发指南](https://docs.astrbot.org/zh/guide/development/start)

---

**提示**: 使用本插件前，请确保已阅读并理解相关配置说明。对于生产环境使用，建议先在测试环境中充分验证。

*让服务器状态监控变得既美观又实用！✨*
