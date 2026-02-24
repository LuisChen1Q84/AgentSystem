# Git版本控制

## 功能说明

系统所有改动都通过Git进行版本追踪，每一次改动都有记录，可以追溯，可以回滚。

## 初始化

首次使用时执行：

```bash
cd /Volumes/Luis_MacData/AgentSystem
git init
git add .
git commit -m "Initial commit: AgentSystem v1.0"
```

## 提交规则

### 每次改动必须提交

- 每次创建新文件
- 每次修改文件
- 每次删除文件
- 每次系统迭代

### 提交信息格式

```
git commit -m "type: description"
```

**type类型**：
- `feat`: 新功能
- `fix`: 修复
- `update`: 更新
- `refactor`: 重构
- `docs`: 文档
- `chore`: 杂项

**示例**：
```bash
git commit -m "feat: 添加policy-pbc新工作流"
git commit -m "fix: 修正任务清单格式"
git commit -m "update: 更新技能库"
```

### 自动提交

在以下场景自动提交：
- /done 技能执行时
- 系统迭代完成后
- 重要文件修改后

## 版本历史查看

```bash
git log --oneline
git log --all --graph --decorate
```

## 回滚

```bash
# 回滚到上一个版本
git revert HEAD

# 回滚到指定版本
git revert <commit-id>
```

## 强制规则

- **禁止**直接修改历史
- **禁止**强制推送
- 每次提交**必须**有清晰的说明
