---
description: 图像创作中枢 - 自动路由到角色/场景/产品/风格4类子代理并生成3D风格图像
argument-hint: [需求描述] [--params-json '{"style_id":"..."}']
allowed-tools: Read, Write, Edit, Grep, Bash
model: opus
---

# 图像创作中枢

**触发词**: /image-creator-hub
**说明**: 根据用户意图自动分派到4个子代理并执行图像生成

---

## 核心能力

- 角色类：收藏级动作手办、卡通肖像、Q版/Chibi
- 场景类：城市微缩、地标渲染、电影场景、等轴测房间、天气可视化
- 产品类：贴纸轰炸Logo、Q版品牌店铺、产品3D渲染、产品广告设计
- 风格类：低多边形、表情包转3D、裸眼3D、Knolling、风格化3D角色

---

## 执行入口

- 路由执行：`python3 scripts/skill_router.py execute --text "<用户输入>" --params-json '{}'`
- 直连执行：`python3 scripts/image_creator_hub.py run --text "<用户输入>" --params-json '{}'`
- Make入口：`make image-hub text='...' [params='{"k":"v"}']`

## 后端说明

- provider 优先级：`minimax -> openai_compatible -> mock`
- 默认使用 `MINIMAX_API_KEY` 调用 MiniMax 图片生成接口
- 未配置 key 或接口失败会自动降级，不阻断流程
- 观测入口：`make image-hub-observe [days=7]`
