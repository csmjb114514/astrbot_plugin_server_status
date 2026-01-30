#!/usr/bin/env python3
"""
AstrBot 服务器状态卡片插件
生成美观的二次元毛玻璃风格状态卡片，支持AI分析。
"""

import asyncio
import json
import time
import socket
import base64
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import aiohttp
import psutil
from pythonping import ping as ping_test
from PIL import Image, ImageDraw, ImageFont

from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
import astrbot.api.message_components as Comp
from astrbot.core.utils.astrbot_path import get_astrbot_data_path

@register(
    name="server_status",
    author="AstrBot Developer",
    description="生成美观的服务器状态卡片，支持AI分析",
    version="1.0.0",
    repo_url="https://github.com/astrbot/astrbot_plugin_server_status"
)
class ServerStatusPlugin(Star):
    """
    服务器状态监控插件主类
    功能：监控系统状态，生成可视化卡片，支持AI分析
    """
    
    def __init__(self, context: Context, config: dict):
        """
        插件初始化
        Args:
            context: AstrBot 上下文对象
            config: 插件配置字典
        """
        super().__init__(context)
        self.config = config
        self.session: Optional[aiohttp.ClientSession] = None
        self.cached_status = None
        self.cache_time = 0
        self.cache_duration = config.get("cache_duration", 60)
        
        # 初始化插件数据目录
        self.plugin_dir = get_astrbot_data_path() / "plugin_data" / "server_status"
        self.plugin_dir.mkdir(parents=True, exist_ok=True)
        
        # 模板文件路径
        self.template_dir = Path(__file__).parent / "templates"
        self.template_dir.mkdir(exist_ok=True)
        
        # 字体路径处理
        self.font_path = None
        if config.get("font_path"):
            font_file = Path(__file__).parent / "fonts" / config["font_path"]
            if font_file.exists():
                self.font_path = str(font_file)
                logger.info(f"已加载字体: {self.font_path}")
        
        # 启动定时更新任务（如果配置了）
        update_interval = config.get("update_interval", 5)
        if update_interval > 0:
            self.start_periodic_update(update_interval)
        
        logger.info("服务器状态插件初始化完成")
    
    def start_periodic_update(self, interval_minutes: int):
        """启动定期更新任务"""
        async def update_task():
            interval_seconds = interval_minutes * 60
            while True:
                try:
                    await self.collect_server_status()
                    await asyncio.sleep(interval_seconds)
                except Exception as e:
                    logger.error(f"定期更新失败: {str(e)}")
                    await asyncio.sleep(60)
        
        asyncio.create_task(update_task())
    
    async def collect_server_status(self) -> Dict:
        """
        收集服务器状态信息
        Returns:
            包含所有状态信息的字典
        """
        try:
            status_data = {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "cpu_usage": psutil.cpu_percent(interval=0.5),
                "cpu_count": psutil.cpu_count(),
                "cpu_freq_current": psutil.cpu_freq().current if psutil.cpu_freq() else 0,
                "memory": {
                    "total": psutil.virtual_memory().total,
                    "available": psutil.virtual_memory().available,
                    "percent": psutil.virtual_memory().percent,
                    "used": psutil.virtual_memory().used
                },
                "disk": {
                    "total": psutil.disk_usage('/').total,
                    "used": psutil.disk_usage('/').used,
                    "free": psutil.disk_usage('/').free,
                    "percent": psutil.disk_usage('/').percent
                },
                "boot_time": psutil.boot_time(),
                "servers": []
            }
            
            # 尝试获取CPU温度
            try:
                temps = psutil.sensors_temperatures()
                if temps and 'coretemp' in temps:
                    status_data["cpu_temp"] = temps['coretemp'][0].current
                else:
                    status_data["cpu_temp"] = 0
            except:
                status_data["cpu_temp"] = 0
            
            # 监控服务器连接状态
            servers = self.config.get("monitored_servers", {})
            for name, address in servers.items():
                if isinstance(address, str) and address:
                    server_status = await self.check_server_connection(address)
                    status_data["servers"].append({
                        "name": name,
                        "address": address,
                        **server_status
                    })
            
            # 缓存数据
            self.cached_status = status_data
            self.cache_time = time.time()
            
            # 保存到文件（可选，用于调试）
            if self.config.get("enable_detailed_logs", False):
                cache_file = self.plugin_dir / "status_cache.json"
                with open(cache_file, 'w', encoding='utf-8') as f:
                    json.dump(status_data, f, ensure_ascii=False, indent=2)
            
            logger.debug(f"状态数据已更新: {status_data['timestamp']}")
            return status_data
            
        except Exception as e:
            logger.error(f"收集服务器状态失败: {str(e)}")
            return self.get_fallback_status()
    
    async def check_server_connection(self, address: str) -> Dict:
        """
        检查服务器连接状态
        Args:
            address: 服务器地址，格式为 host:port 或 host
        Returns:
            包含状态、延迟和颜色的字典
        """
        try:
            timeout = self.config.get("ping_timeout", 3)
            
            # 如果是 host:port 格式，尝试TCP连接
            if ':' in address:
                host, port_str = address.split(':', 1)
                try:
                    port = int(port_str)
                    start_time = time.time()
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(timeout)
                    result = sock.connect_ex((host, port))
                    latency = (time.time() - start_time) * 1000
                    sock.close()
                    
                    if result == 0:
                        return {
                            "status": "online",
                            "latency": round(latency, 1),
                            "latency_color": self.get_latency_color(latency)
                        }
                except (ValueError, socket.error):
                    pass
            
            # 尝试Ping（适用于任何地址）
            try:
                result = ping_test(address, count=1, timeout=timeout)
                if result.success():
                    return {
                        "status": "online",
                        "latency": round(result.rtt_avg_ms, 1),
                        "latency_color": self.get_latency_color(result.rtt_avg_ms)
                    }
            except:
                pass
            
            # 所有检测都失败，视为离线
            return {
                "status": "offline",
                "latency": 0,
                "latency_color": self.config.get("color_scheme", {}).get("error", "#ff4500")
            }
            
        except Exception as e:
            logger.warning(f"检查服务器 {address} 失败: {str(e)}")
            return {
                "status": "offline",
                "latency": 0,
                "latency_color": self.config.get("color_scheme", {}).get("error", "#ff4500")
            }
    
    def get_latency_color(self, latency: float) -> str:
        """根据延迟获取颜色"""
        colors = self.config.get("color_scheme", {})
        threshold = self.config.get("latency_warning_threshold", 150)
        
        if latency < 50:
            return colors.get("success", "#32cd32")
        elif latency < threshold:
            return colors.get("warning", "#ffa500")
        else:
            return colors.get("error", "#ff4500")
    
    def get_usage_color(self, usage: float) -> str:
        """根据使用率获取颜色"""
        colors = self.config.get("color_scheme", {})
        threshold = self.config.get("usage_warning_threshold", 85)
        
        if usage < 60:
            return colors.get("success", "#32cd32")
        elif usage < threshold:
            return colors.get("warning", "#ffa500")
        else:
            return colors.get("error", "#ff4500")
    
    def get_fallback_status(self) -> Dict:
        """获取备用状态数据（当主要监控失败时）"""
        return {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "cpu_usage": 0,
            "cpu_count": 0,
            "cpu_freq_current": 0,
            "memory": {"total": 0, "available": 0, "percent": 0, "used": 0},
            "disk": {"total": 0, "used": 0, "free": 0, "percent": 0},
            "cpu_temp": 0,
            "boot_time": time.time(),
            "servers": []
        }
    
    def format_uptime(self, seconds: float) -> str:
        """格式化运行时间"""
        days = int(seconds // (24 * 3600))
        hours = int((seconds % (24 * 3600)) // 3600)
        minutes = int((seconds % 3600) // 60)
        
        if days > 0:
            return f"{days}天{hours}小时"
        elif hours > 0:
            return f"{hours}小时{minutes}分钟"
        else:
            return f"{minutes}分钟"
    
    def bytes_to_gb(self, bytes_value: int) -> float:
        """字节转换为GB"""
        return round(bytes_value / (1024 ** 3), 2)
    
    async def get_ai_analysis(self, status_data: Dict) -> str:
        """获取AI分析结果"""
        if not self.config.get("enable_ai_analysis", True):
            return ""
        
        try:
            prompt_template = self.config.get("ai_analysis_prompt", "")
            if not prompt_template:
                return ""
            
            # 准备状态数据文本
            memory = status_data['memory']
            disk = status_data['disk']
            
            status_text = f"""
服务器状态报告 ({status_data['timestamp']})

📊 CPU 状态:
• 使用率: {status_data['cpu_usage']:.1f}%
• 核心数: {status_data['cpu_count']}
• 当前频率: {status_data['cpu_freq_current']:.0f} MHz

💾 内存状态:
• 使用率: {memory['percent']:.1f}%
• 已用: {self.bytes_to_gb(memory['used'])} GB
• 可用: {self.bytes_to_gb(memory['available'])} GB
• 总计: {self.bytes_to_gb(memory['total'])} GB

💿 磁盘状态:
• 使用率: {disk['percent']:.1f}%
• 已用: {self.bytes_to_gb(disk['used'])} GB
• 可用: {self.bytes_to_gb(disk['free'])} GB
• 总计: {self.bytes_to_gb(disk['total'])} GB

🌡️ CPU 温度: {status_data.get('cpu_temp', 0):.1f}°C

🔗 服务器连接:
• 监控服务器数: {len(status_data['servers'])}
• 在线服务器: {sum(1 for s in status_data['servers'] if s['status'] == 'online')}
• 离线服务器: {sum(1 for s in status_data['servers'] if s['status'] == 'offline')}

⏰ 系统运行时间: {self.format_uptime(time.time() - status_data['boot_time'])}
            """
            
            prompt = prompt_template.replace("{status_data}", status_text.strip())
            
            # 获取LLM提供商
            provider_id = await self.context.get_current_chat_provider_id(umo="server_status")
            if not provider_id:
                return "🤖 AI分析功能暂不可用（未配置LLM提供商）"
            
            # 调用LLM
            llm_resp = await self.context.llm_generate(
                chat_provider_id=provider_id,
                prompt=prompt,
                max_tokens=500
            )
            
            # 格式化分析结果
            analysis_text = llm_resp.completion_text.strip()
            return self.format_ai_analysis(analysis_text)
            
        except Exception as e:
            logger.error(f"AI分析失败: {str(e)}")
            return "🤖 AI分析暂时不可用"
    
    def format_ai_analysis(self, analysis_text: str) -> str:
        """格式化AI分析文本"""
        if not analysis_text:
            return ""
        
        lines = analysis_text.strip().split('\n')
        formatted_lines = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # 智能添加表情符号
            if line.startswith(('✅', '✓', '✔', '正确', '良好', '正常', '优秀')):
                line = "✅ " + line.lstrip('✅✓✔ ')
            elif line.startswith(('⚠️', '⚠', '❗', '‼', '注意', '警告', '偏高')):
                line = "⚠️ " + line.lstrip('⚠️⚠❗‼ ')
            elif line.startswith(('❌', '✗', '×', '错误', '危险', '严重', '超标')):
                line = "❌ " + line.lstrip('❌✗× ')
            elif line.startswith(('💡', '🔧', '建议', '推荐', '优化')):
                line = "💡 " + line.lstrip('💡🔧 ')
            elif line.startswith(('📊', '📈', '📉', '统计', '数据')):
                line = "📊 " + line.lstrip('📊📈📉 ')
            else:
                line = "📌 " + line
            
            formatted_lines.append(line)
        
        return '\n'.join(formatted_lines)
    
    def hex_to_rgb(self, hex_color: str) -> str:
        """将十六进制颜色转换为RGB字符串"""
        hex_color = hex_color.lstrip('#')
        if len(hex_color) == 6:
            try:
                r = int(hex_color[0:2], 16)
                g = int(hex_color[2:4], 16)
                b = int(hex_color[4:6], 16)
                return f"{r},{g},{b}"
            except:
                pass
        return "255,255,255"
    
    def load_template(self) -> str:
        """加载HTML模板"""
        try:
            template_file = self.template_dir / "status_card.html"
            if template_file.exists():
                with open(template_file, 'r', encoding='utf-8') as f:
                    return f.read()
        except Exception as e:
            logger.error(f"加载模板失败: {str(e)}")
        
        # 返回备用模板
        return '''
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body { 
                    background: transparent; 
                    font-family: 'Microsoft YaHei', sans-serif;
                    margin: 0;
                    padding: 20px;
                }
                .status-card {
                    background: rgba(255, 255, 255, 0.9);
                    backdrop-filter: blur(10px);
                    border-radius: 20px;
                    padding: 25px;
                    box-shadow: 0 10px 30px rgba(0,0,0,0.1);
                    border: 1px solid rgba(255,255,255,0.3);
                    max-width: 800px;
                    margin: 0 auto;
                }
                .title {
                    color: #8a2be2;
                    font-size: 24px;
                    font-weight: bold;
                    margin-bottom: 20px;
                    text-align: center;
                }
                .stat-item {
                    margin: 15px 0;
                    padding: 10px;
                    background: rgba(0,0,0,0.03);
                    border-radius: 10px;
                }
                .footer {
                    text-align: center;
                    margin-top: 20px;
                    color: #666;
                    font-size: 12px;
                }
            </style>
        </head>
        <body>
            <div class="status-card">
                <div class="title">✨ 服务器状态面板</div>
                <div class="timestamp">🕐 {{timestamp}}</div>
                
                <div class="stat-item">
                    <strong>📊 CPU 使用率:</strong> {{cpu_usage}}%
                </div>
                <div class="stat-item">
                    <strong>💾 内存使用率:</strong> {{memory_usage}}%
                </div>
                <div class="stat-item">
                    <strong>💿 磁盘使用率:</strong> {{disk_usage}}%
                </div>
                
                {% if servers %}
                <div style="margin-top: 20px;">
                    <strong>🔗 服务器状态:</strong>
                    {% for server in servers %}
                    <div style="margin: 5px 0; padding: 5px 10px; background: {% if server.status == 'online' %}#e8f5e9{% else %}#ffebee{% endif %}; border-radius: 5px;">
                        {{server.name}}: {% if server.status == 'online' %}✅ 在线 ({{server.latency}}ms){% else %}❌ 离线{% endif %}
                    </div>
                    {% endfor %}
                </div>
                {% endif %}
                
                <div class="footer">
                    🚀 系统运行时间: {{uptime}} | 最后更新: {{update_time}}
                </div>
            </div>
        </body>
        </html>
        '''
    
    def render_template(self, template: str, data: Dict) -> str:
        """渲染模板"""
        try:
            # 使用Jinja2渲染
            from jinja2 import Template, Environment, BaseLoader
            
            env = Environment(loader=BaseLoader())
            jinja_template = env.from_string(template)
            return jinja_template.render(**data)
            
        except ImportError:
            logger.warning("Jinja2未安装，使用简单替换")
            # 降级：简单替换
            for key, value in data.items():
                placeholder = f"{{{{{key}}}}}"
                if isinstance(value, (dict, list)):
                    value = json.dumps(value, ensure_ascii=False)
                template = template.replace(placeholder, str(value))
            return template
        except Exception as e:
            logger.error(f"模板渲染失败: {str(e)}")
            # 简单替换作为后备
            for key, value in data.items():
                placeholder = f"{{{{{key}}}}}"
                template = template.replace(placeholder, str(value))
            return template
    
    async def generate_status_image(self, render_data: Dict) -> str:
        """生成状态图片"""
        try:
            # 加载模板
            template_content = self.load_template()
            
            # 渲染HTML
            html_content = self.render_template(template_content, render_data)
            
            # 这里调用AstrBot的html渲染功能
            # 注意：实际实现可能需要根据你的AstrBot版本调整
            image_path = await self.html_render(html_content, {})
            
            return image_path
            
        except Exception as e:
            logger.error(f"生成图片失败: {str(e)}")
            # 创建简单的备用图片
            return await self.create_fallback_image(render_data)
    
    async def create_fallback_image(self, data: Dict) -> str:
        """创建备用图片（当HTML渲染失败时）"""
        try:
            width = 800
            height = 600
            
            # 创建图片
            opacity = self.config.get("card_opacity", 0.85)
            bg_color = (255, 255, 255, int(255 * opacity))
            img = Image.new('RGBA', (width, height), bg_color)
            draw = ImageDraw.Draw(img)
            
            # 设置字体
            font_large = None
            font_normal = None
            if self.font_path:
                try:
                    font_large = ImageFont.truetype(self.font_path, 32)
                    font_normal = ImageFont.truetype(self.font_path, 20)
                except:
                    pass
            
            if not font_large:
                font_large = ImageFont.load_default()
                font_normal = ImageFont.load_default()
            
            # 绘制标题
            title = "✨ 服务器状态面板"
            draw.text((width//2 - 100, 50), title, fill=(138, 43, 226), font=font_large)
            
            # 绘制时间
            draw.text((width - 300, 60), data['timestamp'], fill=(100, 100, 100), font=font_normal)
            
            # 绘制状态信息
            y_pos = 150
            stats = [
                ("📊 CPU 使用率", f"{data['cpu_usage']}%", data['cpu_color']),
                ("💾 内存使用率", f"{data['memory_usage']}%", data['memory_color']),
                ("💿 磁盘使用率", f"{data['disk_usage']}%", data['disk_color']),
                ("🌡️ CPU 温度", f"{data['cpu_temp']}°C", data['temp_color']),
            ]
            
            for icon, value, color in stats:
                draw.text((100, y_pos), icon, fill=(0, 0, 0), font=font_normal)
                draw.text((250, y_pos), value, fill=color, font=font_normal)
                
                # 绘制简单进度条
                progress_value = float(value.replace('%', '').replace('°C', ''))
                if '温度' in icon:
                    progress_value = min(progress_value * 2, 100)
                
                bar_width = int(400 * progress_value / 100)
                draw.rectangle([(250, y_pos + 30), (250 + bar_width, y_pos + 40)], 
                              fill=color, outline=color)
                
                y_pos += 80
            
            # 绘制服务器状态
            y_pos += 30
            draw.text((100, y_pos), "🔗 服务器连接状态:", fill=(138, 43, 226), font=font_normal)
            y_pos += 40
            
            for server in data.get('servers', []):
                status_color = (50, 205, 50) if server['status'] == 'online' else (255, 69, 0)
                status_text = f"{server['name']}: {'✅ 在线' if server['status'] == 'online' else '❌ 离线'}"
                if server['status'] == 'online':
                    status_text += f" ({server['latency']}ms)"
                
                draw.text((120, y_pos), status_text, fill=status_color, font=font_normal)
                y_pos += 40
            
            # 保存到临时文件
            import tempfile
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
                img.save(f.name, 'PNG', quality=95)
                return f.name
                
        except Exception as e:
            logger.error(f"创建备用图片失败: {str(e)}")
            # 返回一个错误提示图片路径
            import tempfile
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
                error_img = Image.new('RGB', (400, 200), (255, 200, 200))
                error_draw = ImageDraw.Draw(error_img)
                error_draw.text((50, 80), "图片生成失败", fill=(255, 0, 0))
                error_draw.text((50, 120), str(e)[:50], fill=(100, 100, 100))
                error_img.save(f.name, 'PNG')
                return f.name
    
    # ==================== 指令处理器 ====================
    
    def setup_commands(self):
        """设置触发命令"""
        trigger_str = self.config.get("trigger_commands", "/status,/服务器状态")
        triggers = [cmd.strip() for cmd in trigger_str.split(',') if cmd.strip()]
        
        for trigger in triggers:
            self.add_command_handler(trigger)
    
    def add_command_handler(self, command: str):
        """动态添加命令处理器"""
        async def status_handler(event: AstrMessageEvent, target_server: str = ""):
            await self.handle_status_command(event, target_server)
        
        # 使用AstrBot的filter装饰器
        handler = filter.command(command)(status_handler)
        
        # 将处理器绑定到类实例
        handler_name = f"handle_{command.replace('/', '_').replace(' ', '_')}"
        setattr(self, handler_name, handler)
        return handler
    
    async def handle_status_command(self, event: AstrMessageEvent, target_server: str = ""):
        """处理状态命令"""
        try:
            # 发送等待消息
            waiting_msg = await event.send("🔄 正在收集服务器状态信息，请稍候...")
            
            # 获取状态数据（使用缓存或重新收集）
            current_time = time.time()
            if (self.cached_status and 
                current_time - self.cache_time < self.cache_duration):
                status_data = self.cached_status
                logger.debug("使用缓存的状态数据")
            else:
                status_data = await self.collect_server_status()
                logger.debug("重新收集状态数据")
            
            # 获取AI分析
            ai_analysis = ""
            if self.config.get("enable_ai_analysis", True):
                ai_analysis = await self.get_ai_analysis(status_data)
            
            # 准备渲染数据
            colors = self.config.get("color_scheme", {})
            memory = status_data['memory']
            disk = status_data['disk']
            
            render_data = {
                # 基础配置
                "background_image": self.config.get("card_background", ""),
                "blur_strength": self.config.get("blur_strength", 10),
                "border_radius": self.config.get("border_radius", 20),
                "show_character": self.config.get("show_anime_character", True),
                "character_image": self.config.get("anime_character_url", ""),
                "font_family": "'Microsoft YaHei', sans-serif",
                
                # 颜色
                "background_color": f"rgba(255, 255, 255, {self.config.get('card_opacity', 0.85)})",
                "text_color": colors.get("text", "#333333"),
                "text_color_rgb": self.hex_to_rgb(colors.get("text", "#333333")),
                "primary_color": colors.get("primary", "#8a2be2"),
                "primary_color_rgb": self.hex_to_rgb(colors.get("primary", "#8a2be2")),
                "secondary_color": colors.get("secondary", "#9370db"),
                "secondary_color_rgb": self.hex_to_rgb(colors.get("secondary", "#9370db")),
                "success_color": colors.get("success", "#32cd32"),
                "error_color": colors.get("error", "#ff4500"),
                
                # 状态数据
                "timestamp": status_data["timestamp"],
                "update_time": datetime.now().strftime("%H:%M:%S"),
                "uptime": self.format_uptime(time.time() - status_data["boot_time"]),
                
                # CPU
                "cpu_usage": round(status_data["cpu_usage"], 1),
                "cpu_color": self.get_usage_color(status_data["cpu_usage"]),
                "cpu_count": status_data["cpu_count"],
                "cpu_temp": round(status_data.get("cpu_temp", 0), 1),
                "temp_color": self.get_usage_color(min(status_data.get("cpu_temp", 0) * 2, 100)),
                "temp_percentage": min(status_data.get("cpu_temp", 0) * 2, 100),
                
                # 内存
                "memory_usage": round(memory['percent'], 1),
                "memory_color": self.get_usage_color(memory['percent']),
                "memory_used": self.bytes_to_gb(memory['used']),
                "memory_total": self.bytes_to_gb(memory['total']),
                
                # 磁盘
                "disk_usage": round(disk['percent'], 1),
                "disk_color": self.get_usage_color(disk['percent']),
                "disk_used": self.bytes_to_gb(disk['used']),
                "disk_total": self.bytes_to_gb(disk['total']),
                
                # 服务器列表
                "servers": status_data["servers"],
                
                # AI分析
                "ai_analysis": ai_analysis,
                
                # 模板变量
                **self.config.get("template_variables", {})
            }
            
            # 设置字体
            if self.font_path:
                try:
                    font_family = self.get_font_family_name()
                    if font_family:
                        render_data["font_family"] = font_family
                except:
                    pass
            
            # 生成图片
            image_path = await self.generate_status_image(render_data)
            
            # 删除等待消息
            try:
                await waiting_msg.delete()
            except:
                pass
            
            # 发送图片
            yield event.image_result(image_path)
            
            # 清理临时文件
            try:
                if os.path.exists(image_path):
                    os.remove(image_path)
            except:
                pass
            
        except Exception as e:
            logger.error(f"处理状态命令失败: {str(e)}", exc_info=True)
            yield event.plain_result(f"❌ 生成状态卡片失败: {str(e)}")
    
    def get_font_family_name(self) -> str:
        """获取字体家族名称"""
        if not self.font_path:
            return ""
        
        try:
            from fontTools.ttLib import TTFont
            font = TTFont(self.font_path)
            
            # 尝试获取英文名
            for plat_id, enc_id, lang_id in [(3, 1, 1033), (1, 0, 0)]:
                name_record = font['name'].getName(4, plat_id, enc_id, lang_id)
                if name_record:
                    font_name = str(name_record).strip()
                    if font_name:
                        return f"'{font_name}', 'Microsoft YaHei', sans-serif"
                        
        except:
            pass
        
        return ""
    
    # ==================== 生命周期方法 ====================
    
    @filter.on_astrbot_loaded()
    async def on_bot_loaded(self):
        """Bot加载完成时初始化命令"""
        logger.info("初始化服务器状态插件命令")
        self.setup_commands()
    
    async def html_render(self, html_content: str, data: Dict) -> str:
        """
        HTML渲染方法
        注意：这个方法需要根据你的AstrBot版本实现
        这里提供了一个简化实现
        """
        # 这里调用AstrBot的html渲染功能
        # 实际实现可能需要调整为你的AstrBot版本支持的方式
        
        # 简化版：直接调用父类的text_to_image方法
        try:
            # 尝试使用Star基类的text_to_image方法
            if hasattr(super(), 'text_to_image'):
                image_path = await super().text_to_image(html_content)
                return image_path
        except:
            pass
        
        # 备选方案：生成图片
        return await self.create_fallback_image(data)
    
    async def terminate(self):
        """插件卸载时调用"""
        if self.session:
            await self.session.close()
            self.session = None
        logger.info("服务器状态插件已卸载")


# ==================== 插件导出 ====================
# 这些导出确保AstrBot能正确识别插件

# 标准插件实例创建函数
def create_plugin_instance(context: Context, config: dict) -> ServerStatusPlugin:
    """创建插件实例的工厂函数"""
    return ServerStatusPlugin(context, config)

# 兼容性导出
__plugin__ = ServerStatusPlugin
__all__ = ['ServerStatusPlugin', 'create_plugin_instance', '__plugin__']

# 插件信息（可选）
PLUGIN_INFO = {
    "name": "server_status",
    "version": "1.0.0",
    "author": "AstrBot Developer",
    "description": "服务器状态监控与可视化插件"
}
