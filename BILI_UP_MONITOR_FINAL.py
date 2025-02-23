import os
import json
import time
import random
import requests
import logging
from datetime import datetime

# 配置日志输出到文件和控制台
def setup_logger():
    # 创建日志目录
    log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # 日志文件名包含日期
    log_file = os.path.join(log_dir, f'bilibili_monitor_{datetime.now().strftime("%Y%m%d")}.log')
    
    # 配置日志格式
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    
    # 文件处理器
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setFormatter(formatter)
    
    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    
    # 配置根日志记录器
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

# 初始化日志
logger = setup_logger()

class BilibiliMonitor:
    def __init__(self):
        logger.info("初始化B站监控程序...")
        self.api_url = "https://api.bilibili.com/x/space/wbi/arc/search"
        self.data_file = "video_history.json"
        self.up_uids = os.environ.get("BILIBILI_UP_UIDS", "").split(",")
        
        if not self.up_uids or not self.up_uids[0]:
            logger.error("未配置UP主UID，请检查环境变量BILIBILI_UP_UIDS")
            raise ValueError("未配置UP主UID")
        
        logger.info(f"监控的UP主UID列表: {self.up_uids}")
        
        # ... 其他初始化代码保持不变 ...

    def send_notification(self, title, content):
        """发送通知"""
        try:
            # 记录通知内容到日志
            logger.info(f"准备发送通知:\n标题: {title}\n内容: {content}")
            
            if os.environ.get('QL_DIR'):
                try:
                    from notify import send
                    send(title, content)
                    logger.info("青龙面板通知发送成功")
                except Exception as e:
                    logger.error(f"青龙面板通知发送失败: {str(e)}")
                    # 尝试备用通知方式
                    self.send_backup_notification(title, content)
            else:
                logger.info("非青龙环境，直接打印通知信息")
                print(f"{title}\n{content}")
        except Exception as e:
            logger.error(f"发送通知时出错: {str(e)}")

    def send_backup_notification(self, title, content):
        """备用通知方式"""
        try:
            # 获取备用通知配置
            push_plus_token = os.environ.get('PUSH_PLUS_TOKEN')
            if push_plus_token:
                # 使用PushPlus发送通知
                push_url = "http://www.pushplus.plus/send"
                data = {
                    "token": push_plus_token,
                    "title": title,
                    "content": content,
                    "template": "html"
                }
                response = requests.post(push_url, json=data)
                if response.json()["code"] == 200:
                    logger.info("PushPlus通知发送成功")
                else:
                    logger.error(f"PushPlus通知发送失败: {response.text}")
        except Exception as e:
            logger.error(f"发送备用通知时出错: {str(e)}")

    def check_updates(self):
        """检查视频更新"""
        logger.info("开始检查视频更新...")
        start_time = time.time()
        
        try:
            history = self.load_history()
            logger.info(f"成功加载历史记录，包含 {len(history)} 个UP主的信息")
            
            for uid in self.up_uids:
                if not uid.strip():
                    continue
                
                logger.info(f"开始检查UP主 {uid} 的视频更新")
                try:
                    videos = self.get_latest_videos(uid)
                    if not videos:
                        logger.warning(f"未获取到UP主 {uid} 的视频信息")
                        continue

                    up_name = videos[0]["author"]
                    logger.info(f"正在处理UP主 {up_name}({uid}) 的视频")
                    
                    new_videos_count = 0
                    for video in videos:
                        bvid = video["bvid"]
                        if uid not in history or bvid not in history[uid]:
                            new_videos_count += 1
                            title = f"UP主{up_name}发布新视频啦！"
                            content = (
                                f"标题：{video['title']}\n"
                                f"链接：https://www.bilibili.com/video/{bvid}\n"
                                f"发布时间：{datetime.fromtimestamp(video['created']).strftime('%Y-%m-%d %H:%M:%S')}"
                            )
                            self.send_notification(title, content)
                            
                            if uid not in history:
                                history[uid] = {}
                            history[uid][bvid] = {
                                "title": video["title"],
                                "created": video["created"]
                            }
                    
                    logger.info(f"UP主 {up_name} 检查完成，发现 {new_videos_count} 个新视频")
                    
                    # 每个UP主处理完后保存一次历史记录
                    self.save_history(history)
                    
                except Exception as e:
                    logger.error(f"处理UP主 {uid} 时出错: {str(e)}")
                    continue
            
            end_time = time.time()
            logger.info(f"视频更新检查完成，耗时 {end_time - start_time:.2f} 秒")
            
        except Exception as e:
            logger.error(f"检查更新过程中出错: {str(e)}")

def main():
    try:
        logger.info("开始运行B站视频监控脚本...")
        monitor = BilibiliMonitor()
        monitor.check_updates()
        logger.info("脚本运行完成")
    except Exception as e:
        logger.error(f"脚本运行出错: {str(e)}")

if __name__ == "__main__":
    main()
