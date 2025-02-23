# ... existing code ...

class BilibiliMonitor:
    def __init__(self):
        self.api_url = "https://api.bilibili.com/x/space/wbi/arc/search"  # 更新API地址
        self.data_file = "video_history.json"
        self.up_uids = os.environ.get("BILIBILI_UP_UIDS", "").split(",")
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        ]
        self.proxy = os.environ.get("BILIBILI_PROXY", None)
        self.max_retries = 3
        self.retry_delay = 5
        self.request_delay = 5  # 增加延迟时间

    def get_random_headers(self):
        """获取更完整的请求头"""
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
            "Cookie": os.environ.get("BILIBILI_COOKIE", ""),  # 从环境变量获取Cookie
        }

    def get_latest_videos(self, uid):
        for retry in range(self.max_retries):
            try:
                # 增加随机延迟
                time.sleep(self.request_delay + random.uniform(2, 5))
                
                params = {
                    "mid": uid,
                    "ps": 5,  # 每页数量
                    "tid": 0,
                    "pn": 1,  # 页码
                    "keyword": "",
                    "order": "pubdate",  # 按发布日期排序
                    "platform": "web",
                    "web_location": "1550101",
                    "order_avoided": "true",
                    "w_rid": "".join(random.choices("0123456789abcdef", k=16)),  # 随机w_rid
                    "wts": int(time.time()),  # 时间戳
                }
                
                proxies = {"http": self.proxy, "https": self.proxy} if self.proxy else None
                
                response = requests.get(
                    self.api_url,
                    params=params,
                    headers=self.get_random_headers(),
                    proxies=proxies,
                    timeout=15
                )
                
                # 打印请求信息用于调试
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

# ... existing code ...
