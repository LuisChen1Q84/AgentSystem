#!/bin/bash
# 汉坤金融科技文章定期更新脚本
# 使用方法: ./update_hankun.sh
# 建议设置: crontab -e (每两周执行)
# 更新日志: 2026-02-20 直接爬取官网，无需SerpAPI

# 配置
ARTICLE_DIR="/Users/luis/docs/agreements/hankun_information/hankun_articles"
INDEX_FILE="/Users/luis/docs/agreements/hankun_information/index.md"
TEMP_DIR="/tmp/hankun_update_$$"

# 创建临时目录
mkdir -p "$TEMP_DIR"
mkdir -p "$ARTICLE_DIR"

echo "========== 汉坤金融科技文章更新 =========="
echo "开始时间: $(date)"
echo ""

# ====== 第1步: 获取所有文章ID ======
echo "[1/5] 获取文章列表..."

ids=()
for page in {1..7}; do
  echo "  正在获取第 $page 页..."
  page_ids=$(curl -s -k "https://www.hankunlaw.com/portal/list/index/id/8.html?q=&industry=47&year=&month=&page=$page" -H "User-Agent: Mozilla/5.0" 2>/dev/null | grep -oE 'cid/8/id/[0-9]+\.html' | grep -oE 'id/[0-9]+' | cut -d'/' -f2)

  for id in $page_ids; do
    ids+=("$id")
  done
done

# 去重
unique_ids=($(printf '%s\n' "${ids[@]}" | sort -u))
TOTAL_NEW=${#unique_ids[@]}
echo "  发现文章总数: $TOTAL_NEW"

# ====== 第2步: 对比已有文章 ======
echo ""
echo "[2/5] 对比已有文章..."

# 获取现有文章ID
existing_ids=()
if [ -d "$ARTICLE_DIR" ]; then
  for file in "$ARTICLE_DIR"/*.md; do
    if [ -f "$file" ]; then
      # 从文件内容中提取ID（使用兼容macOS的方式）
      # 匹配模式: cid/8/id/XXXX.html
      id=$(grep -oE 'cid/8/id/[0-9]+' "$file" 2>/dev/null | sed 's|cid/8/id/||' | sed 's|\.html||' | head -1)
      if [ -n "$id" ] && [ "$id" != "8" ]; then
        existing_ids+=("$id")
      fi
    fi
  done
fi

# 去重
unique_existing=($(printf '%s\n' "${existing_ids[@]}" | sort -u))
EXISTING_COUNT=${#unique_existing[@]}
echo "  现有文章数: $EXISTING_COUNT"

# ====== 第3步: 找出新文章 ======
echo ""
echo "[3/5] 检查新文章..."

# 比较找出新ID（排除无效ID如"8"）
new_ids=()
for id in "${unique_ids[@]}"; do
  # 跳过无效ID
  if [ -z "$id" ] || [ "$id" = "8" ] || [ ${#id} -lt 4 ]; then
    continue
  fi

  found=0
  for existing in "${unique_existing[@]}"; do
    if [ "$id" = "$existing" ]; then
      found=1
      break
    fi
  done
  if [ $found -eq 0 ]; then
    new_ids+=("$id")
  fi
done

NEW_COUNT=${#new_ids[@]}

# ====== 第4步: 下载新文章 ======
echo ""
if [ "$NEW_COUNT" -gt 0 ]; then
  echo "[4/5] 下载 $NEW_COUNT 篇新文章..."
  echo ""

  success_count=0
  for id in "${new_ids[@]}"; do
    echo "  [$((success_count+1))/$NEW_COUNT] 下载文章 ID: $id"

    # 获取文章页面
    html=$(curl -s -k "https://www.hankunlaw.com/portal/article/index/cid/8/id/${id}.html" -H "User-Agent: Mozilla/5.0" --connect-timeout 10 --max-time 30)

    if [ -n "$html" ]; then
      # 提取标题
      title=$(echo "$html" | grep -o '<title>[^<]*</title>' | sed 's/<title>//g' | sed 's/<\/title>//g' | sed 's/ - 汉坤律师事务所//g' | sed 's/^ *//g')

      # 提取内容
      content=$(echo "$html" | grep -A300 'class="artContent' | sed 's/<[^>]*>//g' | sed 's/&nbsp;/ /g' | sed 's/&ensp;/ /g' | sed 's/^ *//g')

      if [ -n "$title" ] && [ -n "$content" ]; then
        # 创建文件名
        filename=$(echo "$title" | sed 's/[/\\:*?"<>|]//g' | tr ' ' '_' | cut -c1-50)

        # 写入markdown文件
        cat > "${ARTICLE_DIR}/${filename}.md" << EOF
# ${title}

> 来源：汉坤律师事务所
> 原文链接：https://www.hankunlaw.com/portal/article/index/cid/8/id/${id}.html
> 采集日期：$(date +%Y-%m-%d)

---

${content}
EOF
        echo "    -> 已保存: ${filename}.md"
        success_count=$((success_count + 1))
      else
        echo "    -> 失败: 无法提取内容"
      fi
    else
      echo "    -> 失败: 无法获取页面"
    fi

    # 礼貌性延迟
    sleep 0.5
  done

  echo ""
  echo "  成功下载: $success_count 篇"

else
  echo "[4/5] 没有发现新文章，跳过下载"
fi

# ====== 第5步: 更新索引 ======
echo ""
echo "[5/5] 更新索引文件..."

# 统计当前文章数
current_count=$(ls -1 "$ARTICLE_DIR"/*.md 2>/dev/null | wc -l | tr -d ' ')

# 生成新的索引文件
cat > "$INDEX_FILE" << EOF
# 汉坤金融科技文章索引

> 更新时间：$(date +%Y-%m-%d)
> 文章总数：${current_count} 篇

---

## 文章目录

| 序号 | ID | 标题 |
|------|-----|------|
EOF

# 添加所有文章到索引
index=1
for file in "$ARTICLE_DIR"/*.md; do
  if [ -f "$file" ]; then
    # 从文件内容提取ID和标题（兼容macOS）
    url_id=$(grep -oE 'cid/8/id/[0-9]+' "$file" 2>/dev/null | sed 's|cid/8/id/||' | sed 's|\.html||' | head -1)
    title=$(head -5 "$file" | grep '^# ' | sed 's/^# //')

    if [ -n "$url_id" ] && [ -n "$title" ]; then
      echo "| $index | $url_id | $title |" >> "$INDEX_FILE"
      index=$((index + 1))
    fi
  fi
done

echo "  索引文件已更新: $INDEX_FILE"

# 清理
rm -rf "$TEMP_DIR"

echo ""
echo "========== 更新完成 =========="
echo "结束时间: $(date)"
echo "文章总数: $current_count 篇"
echo "============================================"
