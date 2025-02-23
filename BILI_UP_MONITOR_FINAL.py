import os
import json
import time
import requests
from typing import List, Dict
from datetime import datetime
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class BilibiliMonitor:
    def __init__(self):
        # B站API接口
        self.api_url = "https://api.bilibili.com/x/space/arc/search"
        # 存储文件路径
        self.data_file = "video_history.json"
        # 从环境变量获取UP主UID列表
        self.up_uids = os.environ.get("BILIBILI_UP_UIDS", "").split(",")
        # 请求头
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

    def get_latest_videos(self, uid: str) -> List[Dict]:
        """获取UP主最新视频信息"""
        try:
            params = {
                "mid": uid,
                "ps": 5,  # 获取最新5个视频
                "pn": 1
            }
            response = requests.get(self.api_url, params=params, headers=self.headers)
            response.raise_for_status()
            data = response.json()
            
            if data["code"] == 0:
                return data["data"]["list"]["vlist"]
            else:
                logger.error(f"获取视频信息失败: {data['message']}")
                return []
                
        except Exception as e:
            logger.error(f"请求API出错: {str(e)}")
            return []

    def load_history(self) -> Dict:
        """加载历史记录"""
        try:
            if os.path.exists(self.data_file):
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            logger.error(f"加载历史记录失败: {str(e)}")
            return {}

    def save_history(self, history: Dict):
        """保存历史记录"""
        try:
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存历史记录失败: {str(e)}")

    def send_notification(self, title: str, content: str):
        """发送通知"""
        try:
            # 判断是否在青龙环境中
            if os.environ.get('QL_DIR'):
                # 使用青龙通知
                from notify import send
                send(title, content)
            else:
                # 本地测试时直接打印
                print(f"{title}\n{content}")
        except Exception as e:
            logger.error(f"发送通知失败: {str(e)}")

    def check_updates(self):
        """检查视频更新"""
        history = self.load_history()
        
        for uid in self.up_uids:
            if not uid.strip():
                continue
                
            videos = self.get_latest_videos(uid)
            if not videos:
                continue

            # 获取UP主名称
            up_name = videos[0]["author"]
            
            # 检查新视频
            for video in videos:
                bvid = video["bvid"]
                if uid not in history or bvid not in history[uid]:
                    # 发现新视频，发送通知
                    title = f"UP主{up_name}发布新视频啦！"
                    content = (f"标题：{video['title']}\n"
                             f"链接：https://www.bilibili.com/video/{bvid}")
                    self.send_notification(title, content)
                    
                    # 更新历史记录
                    if uid not in history:
                        history[uid] = {}
                    history[uid][bvid] = {
                        "title": video["title"],
                        "created": video["created"]
                    }
            
        # 保存更新后的历史记录
        self.save_history(history)

def main():
    monitor = BilibiliMonitor()
    monitor.check_updates()

if __name__ == "__main__":
    main()
