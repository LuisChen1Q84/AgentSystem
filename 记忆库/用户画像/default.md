---
preferences:
  language: 中文
learned_from: []
linked_patterns: []
updated_at: '2026-02-27 13:49:25'
---
# 用户画像

**版本**: v1.0
**说明**: 用户偏好和学习历史的中心存储

---

## 偏好设置

```yaml
preferences:
  # 沟通偏好
  language: "中文"           # 中文 / 英文 / 混排
  output_format: "简洁"      # 简洁 / 详细 / 适中
  detail_level: "深入"        # 深入 / 概要 / 适中

  # 工作偏好
  working_hours: "工作日"    # 工作日 / 全时 / 自定义
  timezone: "Asia/Shanghai"

  # 内容偏好
  preferred_skills: []       # 常用的技能列表
  output_style: "直接"       # 直接 / 委婉 / 幽默

  # 技术偏好
  code_style: "pythonic"    # pythonic / explicit / functional
  file_organization: "按功能" # 按功能 / 按类型 / 混合
```

## 学习历史

记录从交互中学习到的偏好：

```yaml
learned_from:
  - session: "2026-02-27-1"
    type: "explicit_preference"
    preference: "喜欢简洁的回复"
    evidence: "用户说'少废话，直接说重点'"
    accepted: true

  - session: "2026-02-27-2"
    type: "inferred_preference"
    preference: "偏好使用中文回复"
    evidence: "用户全程使用中文交流"
    accepted: false  # 需要用户确认
```

## 模式库引用

关联此用户学习到的模式：

```yaml
linked_patterns:
  - pattern_id: "py-type-hint-missing"
    first_learned: "2026-02-20"
    times_applied: 3
    success_rate: 1.0
```

---

## 更新规则

1. **显式偏好**：用户明确表达的偏好 → 直接采纳
2. **隐式偏好**：从行为推断的偏好 → 标记待确认
3. **冲突处理**：新偏好覆盖旧偏好，保留历史记录

---

*本文件由 AgentSystem Level 3 学习系统自动管理*
