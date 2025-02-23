import os
import json
import time
import random
import requests
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class BilibiliMonitor:
    def __init__(self):
        self.api_url = "https://api.bilibili.com/x/space/arc/search"
        self.data_file = "video_history.json"
        self.up_uids = os.environ.get("BILIBILI_UP_UIDS", "").split(",")
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15",
        ]
        self.proxy = os.environ.get("BILIBILI_PROXY", None)
        self.max_retries = 3
        self.retry_delay = 5
        self.request_delay = 3

    def get_random_headers(self):
        return {
            "User-Agent": random.choice(self.user_agents),
            "Referer": "https://www.bilibili.com",
            "Accept": "application/json, text/plain, */*",
            "Connection": "keep-alive"
        }

    def get_latest_videos(self, uid):
        for retry in range(self.max_retries):
            try:
                time.sleep(self.request_delay + random.uniform(1, 3))
                
                params = {
                    "mid": uid,
                    "ps": 5,
                    "pn": 1,
                    "tid": 0,
                    "order": "pubdate",
                    "jsonp": "jsonp"
                }
                
                proxies = {"http": self.proxy, "https": self.proxy} if self.proxy else None
                
                response = requests.get(
                    self.api_url,
                    params=params,
                    headers=self.get_random_headers(),
                    proxies=proxies,
                    timeout=10
                )
                response.raise_for_status()
                data = response.json()
                
                if data["code"] == 0:
                    return data["data"]["list"]["vlist"]
                elif data["code"] == -412:
                    logger.warning(f"请求被拦截，等待重试 ({retry + 1}/{self.max_retries})")
                    time.sleep(self.retry_delay * (retry + 1))
                    continue
                else:
                    logger.error(f"获取视频信息失败: {data['message']}")
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
        try:
            if os.path.exists(self.data_file):
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            logger.error(f"加载历史记录失败: {str(e)}")
            return {}

    def save_history(self, history):
        try:
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存历史记录失败: {str(e)}")

    def send_notification(self, title, content):
        try:
            if os.environ.get('QL_DIR'):
                from notify import send
                send(title, content)
            else:
                print(f"{title}\n{content}")
        except Exception as e:
            logger.error(f"发送通知失败: {str(e)}")

    def check_updates(self):
        history = self.load_history()
        
        for uid in self.up_uids:
            if not uid.strip():
                continue
            
            try:
                videos = self.get_latest_videos(uid)
                if not videos:
                    continue

                up_name = videos[0]["author"]
                
                for video in videos:
                    bvid = video["bvid"]
                    if uid not in history or bvid not in history[uid]:
                        title = f"UP主{up_name}发布新视频啦！"
                        content = (f"标题：{video['title']}\n"
                                 f"链接：https://www.bilibili.com/video/{bvid}")
                        self.send_notification(title, content)
                        
                        if uid not in history:
                            history[uid] = {}
                        history[uid][bvid] = {
                            "title": video["title"],
                            "created": video["created"]
                        }
                
                self.save_history(history)
                
            except Exception as e:
                logger.error(f"处理UP主 {uid} 时出错: {str(e)}")
                continue

def main():
    monitor = BilibiliMonitor()
    monitor.check_updates()

if __name__ == "__main__":
    main()
