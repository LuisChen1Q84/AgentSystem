# Image Creator Skill Upgrade (2026-02-27)

## 背景

用户反馈文生图/图生图效果偏弱，尤其体现在：
- 图生图参考图利用率不足
- 提示词质量约束不稳定
- 有参考图时仍被必填字段卡住

## 本次优化

1. 图生图输入链路增强
- 本地参考图自动转换 Data URL（Base64）并传给后端
- 统一 reference_files 规范化，避免无效路径直接进入后端
- 输出 route 增加 `generation_mode=text2img|img2img`

2. 必填逻辑优化
- 对图生图场景放宽 required 校验：
  - 有参考图时，不再强制 `character/subject/product/logo_or_brand/meme_description`

3. Prompt 质量增强
- 新增提示词增强器，自动附加质量约束：
  - 主体明确、构图干净、材质真实、光影自然、无水印无文字
- 对图生图自动追加“保持参考图主体身份和轮廓”约束

4. 路由与别名增强
- routes 增补 `图生图/img2img/reference`
- style alias 增补 `图生图 -> stylized_character`

## 配置新增

- `reference_max_count`
- `embed_local_reference_as_data_url`
- `prompt_enhance`
- `prompt_quality_suffix_zh`
- `prompt_quality_suffix_en`

## 测试结果

- `tests/test_image_creator_hub.py`：7/7 通过
- 全量测试：83 tests 通过
- checks：8/8 通过
