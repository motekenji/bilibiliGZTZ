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
        self.data_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'video_history.json')
        self.up_uids = os.environ.get("BILIBILI_UP_UIDS", "").split(",")
        
        if not self.up_uids or not self.up_uids[0]:
            logger.error("未配置UP主UID，请检查环境变量BILIBILI_UP_UIDS")
            raise ValueError("未配置UP主UID")
        
        logger.info(f"监控的UP主UID列表: {self.up_uids}")
        
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        ]
        self.proxy = os.environ.get("BILIBILI_PROXY", None)
        self.max_retries = 3
        self.retry_delay = 5
        self.request_delay = 5

    def get_random_headers(self):
        """获取随机User-Agent"""
        return {
            "User-Agent": random.choice(self.user_agents),
            "Referer": "https://space.bilibili.com",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Origin": "https://space.bilibili.com",
            "Connection": "keep-alive",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-site",
            "Cookie": os.environ.get("BILIBILI_COOKIE", ""),
        }

    def get_latest_videos(self, uid):
        """获取UP主最新视频信息"""
        for retry in range(self.max_retries):
            try:
                time.sleep(self.request_delay + random.uniform(2, 5))
                
                params = {
                    "mid": uid,
                    "ps": 5,
                    "tid": 0,
                    "pn": 1,
                    "keyword": "",
                    "order": "pubdate",
                    "platform": "web",
                    "web_location": "1550101",
                    "order_avoided": "true",
                    "w_rid": "".join(random.choices("0123456789abcdef", k=16)),
                    "wts": int(time.time()),
                }
                
                proxies = {"http": self.proxy, "https": self.proxy} if self.proxy else None
                
                response = requests.get(
                    self.api_url,
                    params=params,
                    headers=self.get_random_headers(),
                    proxies=proxies,
                    timeout=15
                )
                
                logger.info(f"请求URL: {response.url}")
                logger.info(f"状态码: {response.status_code}")
                
                response.raise_for_status()
                data = response.json()
                
                if data["code"] == 0:
                    return data["data"]["list"]["vlist"]
                elif data["code"] == -412:
                    logger.warning(f"请求被拦截，等待重试 ({retry + 1}/{self.max_retries})")
                    time.sleep(self.retry_delay * (retry + 1))
                    continue
                else:
                    logger.error(f"获取视频信息失败: {data.get('message', '未知错误')}")
                    return []
                    
            except Exception as e:
                logger.error(f"请求API出错: {str(e)}")
                if retry < self.max_retries - 1:
                    time.sleep(self.retry_delay * (retry + 1))
                    continue
                return []
            
        logger.error(f"获取UP主 {uid} 的视频信息失败，已达到最大重试次数")
        return []

    def load_history(self):
        """加载历史记录"""
        try:
            if os.path.exists(self.data_file):
                logger.info(f"从文件加载历史记录: {self.data_file}")
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    history = json.load(f)
                logger.info(f"成功加载历史记录，包含 {len(history)} 个UP主的信息")
                return history
            else:
                logger.info("历史记录文件不存在，创建新的历史记录")
                return {}
        except Exception as e:
            logger.error(f"加载历史记录失败: {str(e)}")
            return {}

    def save_history(self, history):
        """保存历史记录"""
        try:
            logger.info(f"保存历史记录到文件: {self.data_file}")
            os.makedirs(os.path.dirname(self.data_file), exist_ok=True)
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(history, f, ensure_ascii=False, indent=2)
            logger.info("历史记录保存成功")
        except Exception as e:
            logger.error(f"保存历史记录失败: {str(e)}")

    def send_notification(self, title, content):
        """发送通知"""
        try:
            logger.info(f"准备发送通知:\n标题: {title}\n内容: {content}")
            
            if os.environ.get('QL_DIR'):
                try:
                    from notify import send
                    send(title, content)
                    logger.info("青龙面板通知发送成功")
                except Exception as e:
                    logger.error(f"青龙面板通知发送失败: {str(e)}")
                    self.send_backup_notification(title, content)
            else:
                logger.info("非青龙环境，直接打印通知信息")
                print(f"{title}\n{content}")
        except Exception as e:
            logger.error(f"发送通知时出错: {str(e)}")

    def send_backup_notification(self, title, content):
        """备用通知方式"""
        try:
            push_plus_token = os.environ.get('PUSH_PLUS_TOKEN')
            if push_plus_token:
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
