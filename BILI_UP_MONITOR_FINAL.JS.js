const axios = require('axios');
const crypto = require('crypto');
const fs = require('fs');
const path = require('path');

// 配置参数
const config = {
  BILI_UP_IDS: process.env.BILI_UP_IDS?.split(',') || []
};

// 持久化存储
const DATA_FILE = path.join(__dirname, 'bili_latest_video.json');
let latestData = loadData();

// 加载历史数据
function loadData() {
  try {
    return JSON.parse(fs.readFileSync(DATA_FILE, 'utf8'));
  } catch (e) {
    return {};
  }
}

// 获取WBI签名密钥
async function getWbiKeys() {
  try {
    const response = await axios.get('https://api.bilibili.com/x/web-interface/nav', {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
      },
      timeout: 5000
    });
    
    const imgKey = response.data?.data?.wbi_img?.img_url?.split('/').pop()?.split('.')[0] || '';
    const subKey = response.data?.data?.wbi_img?.sub_url?.split('/').pop()?.split('.')[0] || '';
    
    if (!imgKey || !subKey) throw new Error('获取WBI密钥失败');
    return { imgKey, subKey };
  } catch (e) {
    throw new Error(`获取签名密钥失败: ${e.message}`);
  }
}

// 生成签名参数
function generateSignedParams(params, imgKey, subKey) {
  // 混合密钥
  const mixinKey = [...imgKey, ...subKey].sort().join('').slice(0,32);
  
  // 参数排序
  const sortedParams = Object.keys(params)
    .sort()
    .reduce((acc, key) => {
      acc[key] = encodeURIComponent(params[key]);
      return acc;
    }, {});

  // 构造查询字符串
  const query = new URLSearchParams(sortedParams).toString();
  
  // 计算MD5
  const hash = crypto.createHash('md5')
    .update(query + mixinKey)
    .digest('hex');

  return {
    ...params,
    w_rid: hash
  };
}

// 获取最新视频（带自动签名）
async function getLatestVideo(uid) {
  try {
    // 获取动态密钥
    const { imgKey, subKey } = await getWbiKeys();
    
    // 基础参数
    const baseParams = {
      mid: uid,
      ps: 1,
      pn: 1,
      order: 'pubdate',
      platform: 'web',
      wts: Math.floor(Date.now() / 1000)
    };

    // 生成签名参数
    const signedParams = generateSignedParams(baseParams, imgKey, subKey);
    
    // 请求API
    const response = await axios.get('https://api.bilibili.com/x/space/wbi/arc/search', {
      params: signedParams,
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': `https://space.bilibili.com/${uid}/`
      },
      timeout: 8000
    });

    // 解析数据
    const videoData = response.data?.data?.list?.vlist?.[0];
    if (!videoData) throw new Error('未找到视频数据');
    
    return {
      bvid: videoData.bvid,
      title: videoData.title,
      author: videoData.author
    };
  } catch (e) {
    console.error(`请求失败: ${e.message}`);
    throw new Error('获取视频信息失败');
  }
}

// 发送通知（保持原逻辑）
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

// 执行检测
checkUpdate();
