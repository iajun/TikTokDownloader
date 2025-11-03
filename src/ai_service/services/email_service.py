"""
邮件发送服务
用于发送视频信息和总结文档到订阅邮箱
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from typing import Optional, List
import os
from dotenv import load_dotenv
from pathlib import Path
import tempfile

# 尝试导入 markdown 库，如果没有则使用简单的转换
try:
    import markdown
    HAS_MARKDOWN = True
except ImportError:
    HAS_MARKDOWN = False
    print("Warning: markdown library not found, using simple text conversion")

# 加载 .env 文件
BASE_DIR = Path(__file__).parent.parent.parent.parent
env_path = BASE_DIR / ".env"
load_dotenv(env_path)


class EmailService:
    """邮件发送服务"""
    
    def __init__(self):
        """初始化邮件服务"""
        self.smtp_host = os.getenv("SMTP_HOST", "smtp.qq.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_user = os.getenv("SMTP_USER", "")
        self.smtp_password = os.getenv("SMTP_PASSWORD", "")
        self.from_email = os.getenv("SMTP_FROM_EMAIL", self.smtp_user)
        self.from_name = os.getenv("SMTP_FROM_NAME", "TikTok下载器")
        # SSL模式：如果端口是465，使用SSL；如果端口是587，使用STARTTLS
        self.use_ssl = os.getenv("SMTP_USE_SSL", "").lower() in ("true", "1", "yes")
        # 如果未指定SSL模式，根据端口自动判断
        if not os.getenv("SMTP_USE_SSL"):
            self.use_ssl = (self.smtp_port == 465)
        
    def is_configured(self) -> bool:
        """检查邮件服务是否已配置"""
        return bool(self.smtp_user and self.smtp_password)
    
    def _markdown_to_html(self, markdown_text: str) -> str:
        """将 Markdown 文本转换为 HTML
        
        Args:
            markdown_text: Markdown 格式的文本
        
        Returns:
            HTML 格式的文本
        """
        if HAS_MARKDOWN:
            try:
                # 使用 markdown 库进行转换，支持扩展
                md = markdown.Markdown(extensions=['extra', 'codehilite', 'nl2br'])
                html = md.convert(markdown_text)
                return html
            except Exception as e:
                print(f"Markdown转换失败，使用简单转换: {str(e)}")
                # 如果转换失败，使用简单转换
                return self._simple_text_to_html(markdown_text)
        else:
            # 如果没有 markdown 库，使用简单转换
            return self._simple_text_to_html(markdown_text)
    
    def _simple_text_to_html(self, text: str) -> str:
        """简单的文本转HTML（当没有markdown库时使用）
        
        Args:
            text: 纯文本
        
        Returns:
            HTML 格式的文本
        """
        import html as html_module
        import re
        
        # 简单的转换规则
        lines = text.split('\n')
        html_lines = []
        in_code_block = False
        in_list = False
        
        for line in lines:
            stripped = line.strip()
            
            # 代码块
            if stripped.startswith('```'):
                if in_list:
                    html_lines.append('</ul>')
                    in_list = False
                in_code_block = not in_code_block
                if in_code_block:
                    html_lines.append('<pre><code>')
                else:
                    html_lines.append('</code></pre>')
                continue
            
            if in_code_block:
                # 在代码块中，直接转义HTML特殊字符
                html_lines.append(html_module.escape(line))
                continue
            
            # 标题
            if stripped.startswith('# '):
                if in_list:
                    html_lines.append('</ul>')
                    in_list = False
                html_lines.append(f'<h1>{html_module.escape(stripped[2:])}</h1>')
            elif stripped.startswith('## '):
                if in_list:
                    html_lines.append('</ul>')
                    in_list = False
                html_lines.append(f'<h2>{html_module.escape(stripped[3:])}</h2>')
            elif stripped.startswith('### '):
                if in_list:
                    html_lines.append('</ul>')
                    in_list = False
                html_lines.append(f'<h3>{html_module.escape(stripped[4:])}</h3>')
            elif stripped.startswith('#### '):
                if in_list:
                    html_lines.append('</ul>')
                    in_list = False
                html_lines.append(f'<h4>{html_module.escape(stripped[5:])}</h4>')
            # 列表项
            elif stripped.startswith('- ') or stripped.startswith('* '):
                if not in_list:
                    html_lines.append('<ul>')
                    in_list = True
                # 处理列表项中的粗体
                item_text = html_module.escape(stripped[2:])
                # 简单的粗体处理：**text** -> <strong>text</strong>
                item_text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', item_text)
                html_lines.append(f'<li>{item_text}</li>')
            # 空行
            elif not stripped:
                if in_list:
                    html_lines.append('</ul>')
                    in_list = False
                html_lines.append('<br>')
            else:
                if in_list:
                    html_lines.append('</ul>')
                    in_list = False
                # 处理段落中的粗体
                para_text = html_module.escape(line)
                # 简单的粗体处理：**text** -> <strong>text</strong>
                para_text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', para_text)
                # 简单的斜体处理：*text* -> <em>text</em>（但不在列表中的）
                para_text = re.sub(r'(?<!\*)\*([^*]+?)\*(?!\*)', r'<em>\1</em>', para_text)
                html_lines.append(f'<p>{para_text}</p>')
        
        # 闭合未闭合的标签
        if in_list:
            html_lines.append('</ul>')
        
        return '\n'.join(html_lines)
    
    def send_summary_email(
        self,
        to_email: str,
        video_info: dict,
        summary_content: str
    ) -> bool:
        """发送视频总结邮件
        
        Args:
            to_email: 接收邮箱
            video_info: 视频信息字典（包含 desc, platform, url, nickname 等）
            summary_content: 总结内容（Markdown格式）
        
        Returns:
            是否发送成功
        """
        if not self.is_configured():
            print("邮件服务未配置，跳过发送")
            return False
        
        try:
            # 创建邮件
            msg = MIMEMultipart()
            msg['From'] = f"{self.from_name} <{self.from_email}>"
            msg['To'] = to_email
            msg['Subject'] = f"视频总结完成 - {video_info.get('desc', '无标题')[:50]}"
            
            # 将 Markdown 转换为 HTML
            summary_html = self._markdown_to_html(summary_content)
            
            # 构建邮件正文
            platform_text = "抖音" if video_info.get('platform') == 'douyin' else "TikTok"
            body = f"""
<h2>视频总结已完成</h2>

<h3>视频信息</h3>
<ul>
    <li><strong>平台：</strong>{platform_text}</li>
    <li><strong>标题：</strong>{video_info.get('desc', '无标题')}</li>
    <li><strong>作者：</strong>{video_info.get('nickname', '未知')}</li>
    <li><strong>视频链接：</strong><a href="{video_info.get('share_url', video_info.get('url', ''))}">{video_info.get('share_url', video_info.get('url', '无链接'))}</a></li>
    <li><strong>点赞数：</strong>{video_info.get('digg_count', 0)}</li>
    <li><strong>评论数：</strong>{video_info.get('comment_count', 0)}</li>
    <li><strong>分享数：</strong>{video_info.get('share_count', 0)}</li>
</ul>

<h3>AI总结</h3>
<div style="background-color: #f5f5f5; padding: 15px; border-radius: 5px; margin: 10px 0; line-height: 1.6;">
    {summary_html}
</div>

<hr>
<p style="color: #999; font-size: 12px;">此邮件由TikTok下载器自动发送</p>
"""
            
            msg.attach(MIMEText(body, 'html', 'utf-8'))
            
            # 创建总结文档附件（Markdown格式）
            summary_attachment = MIMEText(summary_content, 'plain', 'utf-8')
            summary_attachment.add_header(
                'Content-Disposition',
                'attachment',
                filename=f"summary_{video_info.get('video_id', 'unknown')}.md"
            )
            msg.attach(summary_attachment)
            
            # 发送邮件
            # 根据端口和配置选择连接方式
            server = None
            connection_success = False
            try:
                if self.use_ssl:
                    # 使用SSL连接（通常用于端口465）
                    print(f"尝试使用SSL连接到 {self.smtp_host}:{self.smtp_port}")
                    server = smtplib.SMTP_SSL(self.smtp_host, self.smtp_port, timeout=30)
                else:
                    # 使用普通SMTP连接，然后启用STARTTLS（通常用于端口587）
                    print(f"尝试连接到 {self.smtp_host}:{self.smtp_port}")
                    server = smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=30)
                    print(f"启用STARTTLS...")
                    server.starttls()  # 启用TLS加密
                    print(f"STARTTLS成功")
                
                # 登录
                print(f"尝试登录到SMTP服务器...")
                server.login(self.smtp_user, self.smtp_password)
                print(f"登录成功")
                
                # 发送邮件
                print(f"发送邮件到 {to_email}...")
                server.send_message(msg)
                print(f"邮件已成功发送到 {to_email}")
                
                # 正常关闭连接
                server.quit()
                connection_success = True
                return True
                
            except smtplib.SMTPConnectError as e:
                print(f"连接SMTP服务器失败: {str(e)}")
                # 如果使用STARTTLS失败且未使用SSL，尝试使用SSL
                if not self.use_ssl:
                    print(f"STARTTLS连接失败，尝试使用SSL连接...")
                    try:
                        if server:
                            try:
                                server.quit()
                            except:
                                pass
                        server = smtplib.SMTP_SSL(self.smtp_host, self.smtp_port, timeout=30)
                        server.login(self.smtp_user, self.smtp_password)
                        server.send_message(msg)
                        server.quit()
                        print(f"邮件已成功发送到 {to_email}（使用SSL）")
                        return True
                    except Exception as e2:
                        print(f"SSL连接也失败: {str(e2)}")
                        raise e
                raise
            except smtplib.SMTPAuthenticationError as e:
                print(f"SMTP认证失败: {str(e)}")
                raise
            except smtplib.SMTPServerDisconnected as e:
                print(f"SMTP服务器连接断开: {str(e)}")
                # 如果使用STARTTLS失败，尝试使用SSL
                if not self.use_ssl:
                    print(f"STARTTLS连接断开，尝试使用SSL连接...")
                    try:
                        if server:
                            try:
                                server.quit()
                            except:
                                pass
                        server = smtplib.SMTP_SSL(self.smtp_host, self.smtp_port, timeout=30)
                        server.login(self.smtp_user, self.smtp_password)
                        server.send_message(msg)
                        server.quit()
                        print(f"邮件已成功发送到 {to_email}（使用SSL）")
                        return True
                    except Exception as e2:
                        print(f"SSL连接也失败: {str(e2)}")
                        raise e
                raise
            except Exception as e:
                print(f"发送邮件时发生错误: {str(e)}")
                raise
            finally:
                # 确保关闭连接
                if server and not connection_success:
                    try:
                        server.quit()
                    except:
                        try:
                            server.close()
                        except:
                            pass
            
        except Exception as e:
            print(f"发送邮件失败: {str(e)}")
            import traceback
            traceback.print_exc()
            return False
    
    def send_batch_summary_emails(
        self,
        to_emails: List[str],
        video_info: dict,
        summary_content: str
    ) -> dict:
        """批量发送视频总结邮件
        
        Args:
            to_emails: 接收邮箱列表
            video_info: 视频信息字典
            summary_content: 总结内容（Markdown格式）
        
        Returns:
            发送结果字典 {email: success}
        """
        results = {}
        for email in to_emails:
            results[email] = self.send_summary_email(
                email, video_info, summary_content
            )
        return results

