#!/bin/bash
# 艾瑞咨询行业报告定期更新脚本（升级版）
# 使用方法: ./update_iresearch_information.sh
# 建议设置: crontab -e (每季度执行)
# 更新周期: 每季度
# 更新主题: 支付、金融科技，反洗钱、防范电信网络诈骗、移动支付、跨境支付、外卡内绑、外包内用

# 配置
ARTICLE_DIR="/Users/luis/docs/agreements/iresearch_information"
API_KEY="fc4717d6c16c54cfa169019d8c7108debaf241becfc4cb4a03c786435d4f17c7"

echo "========== 艾瑞咨询行业报告更新 =========="
echo "开始时间: $(date)"
echo ""

# 搜索主题列表
declare -a topics=(
  "艾瑞咨询 支付 行业报告"
  "艾瑞咨询 金融科技 FinTech"
  "艾瑞咨询 反洗钱"
  "艾瑞咨询 防范电信网络诈骗"
  "艾瑞咨询 移动支付"
  "艾瑞咨询 跨境支付"
  "艾瑞咨询 外卡内绑"
  "艾瑞咨询 外包内用"
)

total_reports=0

for topic in "${topics[@]}"; do
  echo "搜索: $topic"

  # URL编码
  encoded_topic=$(python3 -c "import urllib.parse; print(urllib.parse.quote('$topic'))")

  result=$(curl -s "https://serpapi.com/search.json?api_key=${API_KEY}&q=${encoded_topic}&num=10" 2>/dev/null)

  if [ -n "$result" ]; then
    # 创建文件名
    topic_filename=$(echo "$topic" | sed 's/艾瑞咨询 //g' | sed 's/ /_/g')
    topic_file="${ARTICLE_DIR}/${topic_filename}.md"

    # 写入文件
    echo "# 艾瑞咨询 - $topic 报告" > "$topic_file"
    echo "" >> "$topic_file"
    echo "> 更新日期：$(date +%Y-%m-%d)" >> "$topic_file"
    echo "" >> "$topic_file"
    echo "---" >> "$topic_file"
    echo "" >> "$topic_file"

    # 解析JSON并写入表格
    echo "$result" | python3 -c "
import json, sys
d = json.load(sys.stdin)
print('| 报告名称 | 链接 |')
print('|----------|------|')
for r in d.get('organic_results', [])[:10]:
    title = r.get('title', 'N/A').replace('|', '-')
    link = r.get('link', 'N/A')
    print(f'| {title} | [查看]({link}) |')
" >> "$topic_file"

    # 统计
    count=$(echo "$result" | python3 -c "import json,sys; print(len(json.load(sys.stdin).get('organic_results', [])))")
    total_reports=$((total_reports + count))
    echo "  -> 保存: ${topic_filename}.md ($count 篇)"
  fi

  sleep 1
done

echo ""
echo "[2/3] 生成行业报告汇编..."

# 生成综合汇编
cat > "${ARTICLE_DIR}/艾瑞咨询行业报告汇编.md" << 'EOF'
# 艾瑞咨询行业报告汇编

> 更新日期：2026-02-20
> 来源：通过 SerpAPI 搜索获取
> 更新周期：每季度

---

## 报告分类索引

| 主题 | 文件 |
|------|------|
| 支付行业 | 支付_行业报告.md |
| 金融科技 | 金融科技_FinTech.md |
| 反洗钱 | 反洗钱.md |
| 防范电信网络诈骗 | 防范电信网络诈骗.md |
| 移动支付 | 移动支付.md |
| 跨境支付 | 跨境支付.md |
| 外卡内绑 | 外卡内绑.md |
| 外包内用 | 外包内用.md |

---

## 核心数据汇总

### 支付行业（来自艾瑞咨询报告）

- 2025年中国第三方综合支付交易规模预计达到 **577万亿元**，同比增长3.0%
- 个人支付交易规模增长2.9%
- 企业支付交易规模增长3.2%
- 企业支付增速已经超过个人支付
- 2025年中国产业支付市场规模预计达到 **126.2万亿元**

### 金融科技

- 金融科技市场规模预计将以约 **13.3%** 的复合增长率于2028年突破 **6500亿元**
- 技术趋势：AI、大数据、云服务、区块链

---

## 搜索关键词

- 艾瑞咨询 支付 行业报告
- 艾瑞咨询 金融科技 FinTech
- 艾瑞咨询 反洗钱
- 艾瑞咨询 防范电信网络诈骗
- 艾瑞咨询 移动支付
- 艾瑞咨询 跨境支付
- 艾瑞咨询 外卡内绑
- 艾瑞咨询 外包内用

EOF

echo "  汇编文件已更新"

echo ""
echo "[3/3] 更新索引..."

# 生成索引
cat > "${ARTICLE_DIR}/index.md" << EOF
# 艾瑞咨询研究报告索引

> 更新时间：$(date +%Y-%m-%d)
> 报告数量：${total_reports} 篇

---

## 目录结构

\`\`\`
iresearch_information/
├── index.md                        # 本索引
├── 艾瑞咨询行业报告汇编.md        # 综合汇编
├── 支付_行业报告.md               # 支付行业报告
├── 金融科技_FinTech.md            # 金融科技报告
├── 反洗钱.md                      # 反洗钱报告
├── 防范电信网络诈骗.md            # 防范电信诈骗报告
├── 移动支付.md                   # 移动支付报告
├── 跨境支付.md                   # 跨境支付报告
├── 外卡内绑.md                   # 外卡内绑报告
└── 外包内用.md                   # 外包内用报告
\`\`\`

## 更新日志

| 日期 | 操作 |
|------|------|
| 2026-02-20 | 初始化，创建各主题报告 |

---

## 使用说明

1. 每个主题的搜索结果保存为独立的 markdown 文件
2. 综合汇编文件汇总核心数据
3. 每季度通过 SerpAPI 更新最新报告

EOF

echo "  索引已更新"

echo ""
echo "========== 更新完成 =========="
echo "结束时间: $(date)"
echo "报告总数: $total_reports 篇"
echo "============================================"
