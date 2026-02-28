# mckinsey-ppt 升级说明（2026-02-28）

## 升级判断
- 参考了 [mgechev/skills-best-practices](https://github.com/mgechev/skills-best-practices) 的方法论后，结论是：
  - 该仓库适合借鉴 `skill 结构、渐进加载、脚本化验证` 的思路。
  - 它不是 PPT 渲染项目，不适合直接克隆进本模块解决“HTML 不高级”的问题。

## 本次升级目标
- 保留现有 `deck spec` 能力。
- 新增真正的 premium HTML 预览层，先把“审美、层级、版式”做对。
- 用参考资产和布局目录约束 PPT 技能，而不是继续依赖大段提示词临场发挥。

## 本次改动
- 重构 [scripts/mckinsey_ppt_engine.py](/Volumes/Luis_MacData/AgentSystem/scripts/mckinsey_ppt_engine.py)
  - 输入解析扩展为 `brand/theme/style/decision_ask/key_metrics/must_include`
  - 统一输出 `storyline / slides / quality_review / reference_digest`
  - 每页增加 `section/layout/decision_link/visual_brief/evidence_needed`
- 新增 [scripts/mckinsey_ppt_html_renderer.py](/Volumes/Luis_MacData/AgentSystem/scripts/mckinsey_ppt_html_renderer.py)
  - 输出高保真 `deck_preview_*.html`
  - 重点解决层级、留白、风格一致性和审阅体验
- 新增静态资产：
  - [layout_catalog.json](/Volumes/Luis_MacData/AgentSystem/assets/mckinsey_ppt/layout_catalog.json)
  - [design_rules.md](/Volumes/Luis_MacData/AgentSystem/references/mckinsey_ppt/design_rules.md)
  - [story_patterns.md](/Volumes/Luis_MacData/AgentSystem/references/mckinsey_ppt/story_patterns.md)

## 结果
- PPT 子系统从“内容策划器”升级成“内容策划 + premium HTML 预览”的双层结构。
- HTML 预览现在可以作为正式审稿入口，而不是只看 JSON/Markdown。
- 后续若继续升级 PPTX 导出，可以直接复用这份 deck spec 和 layout catalog。

## 第二轮优化（同日继续）
- 扩展主题体系：
  - `boardroom-signal`
  - `ivory-ledger`
  - `harbor-brief`
- 新增 `design_handoff`：
  - `theme_summary`
  - `review_sequence`
  - `html_review_focus`
  - `asset_requests`
  - `slide_navigation`
- 每页新增 `designer_handoff`，让设计师或后续导出器能直接消费：
  - `primary_visual`
  - `module_priority`
  - `headline_density_flag`
  - `accent_targets`
  - `asset_requests`
- HTML 审稿界面新增：
  - 左侧 review rail
  - slide map 导航
  - designer brief
  - handoff strip
  - 更强的质量/风险提示

## 第三轮优化（原生 PPTX 导出）
- 新增 [mckinsey_ppt_pptx_renderer.py](/Volumes/Luis_MacData/AgentSystem/scripts/mckinsey_ppt_pptx_renderer.py)
  - 不依赖 `python-pptx`
  - 直接生成原生 `.pptx`（Open XML）
- 当前产物链路升级为：
  - `deck_spec_*.json`
  - `deck_spec_*.md`
  - `deck_preview_*.html`
  - `deck_native_*.pptx`
- 这一步的目标不是复杂图表自动化，而是先打通：
  - deck spec
  - HTML 审稿
  - native PPTX 交付
  的闭环

## 第四轮优化（PPTX 版式差异化）
- PPTX 不再对所有内容页套一个统一模板。
- 已按关键页型做差异化输出：
  - `executive_summary`
  - `benchmark_matrix`
  - `strategic_options`
  - `initiative_portfolio`
  - `roadmap_track`
- 结果是原生 PPTX 里已经开始出现：
  - 三卡摘要页
  - 对标差距页
  - 三方案比较页
  - 四象限组合页
  - 三波路线图页
- 这一步的意义是让最终交付更像真正的咨询 deck，而不是“同一种信息卡片重复 8 次”。

## 后续建议
- 若要继续提升成品质量，下一步应该做 PPTX 原生导出模板，而不是再扩提示词。
- 若要适配多个审美方向，应在 `assets/mckinsey_ppt/` 下继续扩主题与布局，而不是在 engine 里写分支。
