const axios = require('axios');
const fs = require('fs');
const path = require('path');

// 配置参数 (环境变量设置)
const config = {
  BILI_UP_IDS: process.env.BILI_UP_IDS?.split(',') || [] // UP主ID列表:cite[6]
};

// 持久化存储文件
const DATA_FILE = path.join(__dirname, 'bili_latest_video.json');
let latestData = loadData();

// 备用API列表（自动轮询）
const APIS = [
  uid => `https://bili-api-proxy.vercel.app/space/${uid}/video`,  // 推荐
  uid => `https://api.bilibili.workers.dev/space/${uid}/video`,   // 公益接口1
  uid => `https://bili-proxy.noki.workers.dev/space/${uid}/video` // 公益接口2
];

// 加载历史数据
function loadData() {
  try {
    return JSON.parse(fs.readFileSync(DATA_FILE, 'utf8'));
  } catch (e) {
    return {};
  }
}

// 获取最新视频 (多API容灾)
async function getLatestVideo(uid) {
  for (const api of APIS) {
    try {
      const response = await axios.get(api(uid), { timeout: 5000 });
      if (response.data?.data?.list?.vlist?.[0]) {
        return response.data.data.list.vlist[0];
      }
    } catch (e) {
      console.error(`API [${api(uid)}] 请求失败: ${e.message}`);
    }
  }
  throw new Error('所有API均不可用');
}

// 发送青龙通知
function sendNotify(video) {
  console.log(`[B站更新] UP主 ${video.author} 发布新视频`);
  console.log(`标题: ${video.title}\n链接: https://www.bilibili.com/video/${video.bvid}`);
}

// 检测更新逻辑
async function checkUpdate() {
  for (const uid of config.BILI_UP_IDS) {
    try {
      const video = await getLatestVideo(uid);
      if (!latestData[uid] || latestData[uid] !== video.bvid) {
        sendNotify(video);
        latestData[uid] = video.bvid;
        fs.writeFileSync(DATA_FILE, JSON.stringify(latestData));
      }
    } catch (e) {
      console.error(`UP主 ${uid} 检测失败: ${e.message}`);
    }
  }
}

// 执行一次检测
checkUpdate();