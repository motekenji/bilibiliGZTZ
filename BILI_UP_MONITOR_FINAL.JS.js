const axios = require('axios');
const crypto = require('crypto');
const fs = require('fs');
const path = require('path');

// 配置参数
const config = {
BILI_UP_IDS: process.env.BILI_UP_IDS?.split(',').filter(Boolean) || [] // 兼容空值
};

// 持久化存储
const DATA_FILE = path.join(__dirname, 'bili_latest_video.json');
let latestData = loadData();

// 调试模式
const DEBUG_MODE = process.env.DEBUG === 'true';

// 加载历史数据
function loadData() {
try {
return JSON.parse(fs.readFileSync(DATA_FILE, 'utf8')) || {};
} catch (e) {
return {};
}
}

// 获取WBI签名密钥（2024年最新接口）
async function getWbiKeys() {
try {
const response = await axios.get('https://api.bilibili.com/x/web-interface/nav', {
headers: {
'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
'Referer': 'https://www.bilibili.com/'
},
timeout: 8000
});

if (DEBUG_MODE) {
console.log('[DEBUG] 密钥响应:', JSON.stringify(response.data));
}

const imgKey = response.data?.data?.wbi_img?.img_key || '';
const subKey = response.data?.data?.wbi_img?.sub_key || '';

if (!imgKey || !subKey) throw new Error('密钥格式异常');
return { imgKey, subKey };
} catch (e) {
console.error('[ERROR] 获取签名密钥失败:', e.message);
throw e;
}
}

// 生成签名参数（最新算法）
function generateSignedParams(params, imgKey, subKey) {
try {
// 混合密钥（最新算法）
const mixinKey = [...imgKey, ...subKey]
.sort(() => Math.random() - 0.5)
.join('')
.slice(0, 32);

// 参数处理
const sortedParams = Object.keys(params)
.sort()
.reduce((acc, key) => {
acc[key] = encodeURIComponent(params[key])
.replace(/%20/g, '+')
.replace(/%2F/g, '/');
return acc;
}, {});

// 构造查询字符串
const query = new URLSearchParams(sortedParams).toString();

// MD5哈希
const hash = crypto.createHash('md5')
.update(query + mixinKey)
.digest('hex');

return {
...params,
w_rid: hash
};
} catch (e) {
console.error('[ERROR] 签名生成失败:', e.message);
throw e;
}
}

// 获取最新视频（带重试机制）
async function getLatestVideo(uid) {
for (let retry = 0; retry < 3; retry++) {
try {
const { imgKey, subKey } = await getWbiKeys();

const baseParams = {
mid: uid,
ps: 1,
pn: 1,
order: 'pubdate',
platform: 'web',
web_location: 1550101, // 新增必要参数
wts: Math.floor(Date.now() / 1000)
};

const signedParams = generateSignedParams(baseParams, imgKey, subKey);

if (DEBUG_MODE) {
console.log(`[DEBUG] 请求参数: ${JSON.stringify(signedParams)}`);
}

const response = await axios.get('https://api.bilibili.com/x/space/wbi/arc/search', {
params: signedParams,
headers: {
'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
'Referer': `https://space.bilibili.com/${uid}/video`
},
timeout: 10000
});

if (DEBUG_MODE) {
console.log('[DEBUG] API响应:', JSON.stringify(response.data));
}

const videoData = response.data?.data?.list?.vlist?.[0];
if (!videoData) throw new Error('视频数据为空');

return {
bvid: videoData.bvid,
title: videoData.title.replace(/<[^>]+>/g, ''), // 清理HTML标签
author: videoData.author
};
} catch (e) {
if (retry === 2) throw e;
console.log(`[WARN] 第${retry + 1}次重试...`);
await new Promise(resolve => setTimeout(resolve, 2000));
}
}
}

// 发送通知（兼容青龙通知面板）
function sendNotify(video) {
console.log(`[BiliNotify] UP主 ${video.author} 发布新视频`);
console.log(`标题：${video.title}`);
console.log(`链接：https://www.bilibili.com/video/${video.bvid}`);
console.log(); // 空行分隔多个通知
}

// 主检测逻辑
async function checkUpdate() {
if (!config.BILI_UP_IDS.length) {
console.log('[WARN] 未配置BILI_UP_IDS环境变量');
return;
}

try {
for (const uid of config.BILI_UP_IDS) {
try {
const video = await getLatestVideo(uid);

if (!latestData[uid]) {
console.log(`[INFO] 首次检测UP主 ${uid}，当前最新视频：${video.bvid}`);
latestData[uid] = video.bvid;
continue;
}

if (latestData[uid] !== video.bvid) {
sendNotify(video);
latestData[uid] = video.bvid;
}
} catch (e) {
console.error(`[ERROR] 检测UP主 ${uid} 失败: ${e.message}`);
}
}

fs.writeFileSync(DATA_FILE, JSON.stringify(latestData));
} catch (e) {
console.error('[ERROR] 全局检测失败:', e.message);
}
}

// 执行检测
checkUpdate();
