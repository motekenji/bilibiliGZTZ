const axios = require('axios');
const crypto = require('crypto');
const fs = require('fs');
const path = require('path');

// 配置参数
const config = {
  BILI_UP_IDS: process.env.BILI_UP_IDS?.split(',').map(uid => uid.trim()).filter(Boolean) || []
};

// 持久化存储
const DATA_FILE = path.join(__dirname, 'bili_latest_video.json');
let latestData = loadData();

// 调试模式
const DEBUG_MODE = process.env.DEBUG === 'true';

// 混淆表（需定期检查有效性）
const MIXIN_KEY_ENC_TAB = [
  46,47,18,2,53,8,23,32,15,50,10,31,58,3,45,35,
  27,43,5,49,33,9,42,19,29,28,14,39,12,38,41,13,
  37,48,7,16,24,55,40,61,26,17,0,1,60,51,30,4,
  22,25,54,21,56,59,6,63,57,62,11,36,20,34,44,52
];

// 加载历史数据
function loadData() {
  try {
    return JSON.parse(fs.readFileSync(DATA_FILE, 'utf8')) || {};
  } catch (e) {
    return {};
  }
}

// 获取WBI签名密钥
async function getWbiKeys() {
  try {
    const response = await axios.get('https://api.bilibili.com/x/web-interface/nav', {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
        'Referer': 'https://www.bilibili.com/'
      },
      timeout: 10000
    });

    if (response.data.code !== 0) {
      throw new Error(`导航接口错误: ${response.data.message}`);
    }

    const wbiImg = response.data?.data?.wbi_img;
    if (!wbiImg?.img_key || !wbiImg?.sub_key) {
      throw new Error('密钥字段不存在');
    }

    return {
      imgKey: wbiImg.img_key,
      subKey: wbiImg.sub_key
    };
  } catch (e) {
    console.error('[ERROR] 获取签名密钥失败:', e.message);
    if (DEBUG_MODE && e.response) {
      console.error('[DEBUG] 错误响应:', e.response.data);
    }
    throw new Error('请检查网络或更新User-Agent');
  }
}

// 生成混合密钥
function generateMixinKey(imgKey, subKey) {
  const mixinKey = [...imgKey, ...subKey];
  if (mixinKey.length < 64) {
    throw new Error('无效的密钥长度');
  }
  return MIXIN_KEY_ENC_TAB
    .map(pos => mixinKey[pos])
    .slice(0, 32)
    .join('');
}

// 生成签名参数
function generateSignedParams(params, imgKey, subKey) {
  try {
    const mixinKey = generateMixinKey(imgKey, subKey);
    
    // 参数排序（不进行编码）
    const sortedParams = Object.keys(params)
      .sort()
      .reduce((acc, key) => {
        acc[key] = params[key];
        return acc;
      }, {});

    const query = new URLSearchParams(sortedParams).toString();
    const hash = crypto.createHash('md5')
      .update(query + mixinKey)
      .digest('hex');

    return { 
      ...sortedParams,
      w_rid: hash
    };
  } catch (e) {
    console.error('[ERROR] 签名生成失败:', e.message);
    throw e;
  }
}

// 获取最新视频
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
        web_location: 1550101,
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
        timeout: 15000
      });

      if (response.data.code !== 0) {
        throw new Error(`接口错误: ${response.data.message}`);
      }

      const videoData = response.data?.data?.list?.vlist?.[0];
      if (!videoData) throw new Error('视频数据为空');
      
      return {
        bvid: videoData.bvid,
        title: videoData.title.replace(/<[^>]+>/g, '').trim(),
        author: videoData.author
      };
    } catch (e) {
      if (DEBUG_MODE) {
        console.error(`[DEBUG] 第${retry + 1}次重试错误:`, e.message);
        if (e.response) console.error('[DEBUG] 响应数据:', e.response.data);
      }
      if (retry === 2) throw new Error(`请求失败: ${e.message}`);
      await new Promise(resolve => setTimeout(resolve, 2000 * (retry + 1)));
    }
  }
}

// 发送通知（需根据青龙环境扩展）
function sendNotify(video) {
  console.log(`[BiliNotify] UP主 ${video.author} 发布新视频`);
  console.log(`标题：${video.title}`);
  console.log(`链接：https://www.bilibili.com/video/${video.bvid}`);
  console.log();
  
  // 此处可添加青龙通知函数，例如：
  // notify.send(`B站新视频通知`, `${video.author} 发布了新视频：${video.title}`);
}

// 主检测逻辑
async function checkUpdate() {
  if (!config.BILI_UP_IDS.length) {
    console.log('[WARN] 请设置BILI_UP_IDS环境变量');
    return;
  }

  try {
    let hasUpdate = false;
    
    for (const uid of config.BILI_UP_IDS) {
      try {
        const video = await getLatestVideo(uid);
        
        if (!latestData[uid]) {
          console.log(`[INIT] 初始化监测 UP${uid}，当前视频：${video.bvid}`);
          latestData[uid] = video.bvid;
          hasUpdate = true;
          continue;
        }

        if (latestData[uid] !== video.bvid) {
          console.log(`[UPDATE] 检测到 UP${uid} 的新视频 ${video.bvid}`);
          sendNotify(video);
          latestData[uid] = video.bvid;
          hasUpdate = true;
        }
      } catch (e) {
        console.error(`[ERROR] 监测 UP${uid} 失败: ${e.message}`);
      }
    }
    
    if (hasUpdate) {
      fs.writeFileSync(DATA_FILE, JSON.stringify(latestData));
      console.log('[INFO] 数据已保存');
    }
  } catch (e) {
    console.error('[FATAL] 全局检测失败:', e.message);
  }
}

// 执行检测
checkUpdate();
