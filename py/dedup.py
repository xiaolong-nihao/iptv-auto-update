#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import os
from collections import defaultdict
from urllib.parse import urlparse

def clean_channel_name(name):
    """
    清理频道名称，提取核心名称用于去重
    """
    # 1. 删除方括号标签 [Pd] [Mt] [Hk] 等
    name = re.sub(r'\[[A-Za-z0-9|]+\]', '', name)
    
    # 2. 删除箭头符号
    name = re.sub(r'[➡️⬇️]', '', name)
    
    # 3. 删除常见后缀（这些不影响频道核心名称）
    suffixes = [
        '咪咕', '高码', '4k', '4K', '欣赏', '频陆', '频晴', 
        'Mttv', 'SXtv', 'Hktv', 'FYtv', '4Gtv', '地波', 
        '广州', '高清', 'HD', '超清', '超', '欣赏',
        'Pdtv', 'Petv', 'SX', 'FY', 'Cx', 'mg', 'mv', 'Pe',
        '频陆', '频测', 'Mttv', 'SXtv', 'Hktv', 'FYtv',
        'Web', '网页', '直播', '频道'
    ]
    for suffix in suffixes:
        name = name.replace(suffix, '')
    
    # 4. 删除特殊符号
    name = re.sub(r'[【】\(\)（）]', '', name)
    
    # 5. 删除多余空格和特殊字符
    name = re.sub(r'[｜|]', '', name)
    name = name.strip()
    
    # 6. 如果名称太长，截取关键部分
    # 例如 "CCTV-01咪咕" -> "CCTV-01"
    if 'CCTV' in name:
        match = re.search(r'(CCTV[-+]?\d+[pP]?)', name)
        if match:
            return match.group(1)
    
    # 7. 处理卫视
    if '卫视' in name:
        match = re.search(r'([\u4e00-\u9fa5]+卫视)', name)
        if match:
            return match.group(1)
    
    return name

def get_source_priority(url, name):
    """
    评估源的质量，分数越高越优
    """
    score = 0
    url_lower = url.lower()
    name_lower = name.lower()
    
    # 1. 4K优先 (最高优先级)
    if '4k' in url_lower or '4k' in name_lower:
        score += 1000
    
    # 2. m3u8 格式
    if '.m3u8' in url_lower:
        score += 500
    
    # 3. http/https 优于 p3p
    if url_lower.startswith('http'):
        score += 200
        if url_lower.startswith('https'):
            score += 100
    
    # 4. 高码率
    if '高码' in name_lower:
        score += 300
    
    # 5. 包含具体域名，更稳定
    if 'raw.githubusercontent.com' in url_lower:
        score += 150
    if 'cdn' in url_lower:
        score += 100
    
    # 6. 不是测试源
    if 'test' in url_lower:
        score -= 100
    
    # 7. 包含完整路径
    if '/' in url and len(url.split('/')) > 3:
        score += 50
    
    # 8. 咪咕源（通常较稳定）
    if '咪咕' in name_lower:
        score += 80
    
    return score

def parse_line(line):
    """
    解析一行，返回 (频道名, URL)
    """
    line = line.strip()
    if not line:
        return None, None
    
    # 跳过分类行
    if '#genre#' in line:
        return None, None
    
    # 查找逗号分隔
    if ',' in line:
        parts = line.split(',', 1)
        name = parts[0].strip()
        url = parts[1].strip() if len(parts) > 1 else ''
        return name, url
    
    return None, None

def deduplicate_sources(input_file, output_file=None):
    """
    主函数：去重并保留最优源
    """
    if output_file is None:
        base, ext = os.path.splitext(input_file)
        output_file = f"{base}_dedup{ext}"
    
    print(f"📂 读取文件: {input_file}")
    
    # 读取所有行
    with open(input_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    print(f"📊 总行数: {len(lines)}")
    
    # 存储最优源
    best_sources = {}  # {核心名称: (原始行, 分数, 原始名称, URL)}
    stats = {
        'total': 0,
        'skipped': 0,
        'kept': 0,
        'duplicates': 0,
        'by_category': defaultdict(int)
    }
    
    # 类别关键词
    categories = {
        '央视': ['CCTV', '央视', '中央'],
        '卫视': ['卫视', '东方', '湖南', '浙江', '江苏', '北京', '深圳'],
        '港澳台': ['凤凰', 'TVB', '翡翠', '明珠', '香港', '澳门', '台湾'],
        '赛事': ['体育', '赛事', 'NBA', '英超', '足球', '篮球'],
        '新闻': ['新闻', '资讯'],
        '电影': ['电影', '影院'],
        '音乐': ['音乐', '歌曲', '串烧'],
        '其他': []
    }
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        stats['total'] += 1
        
        # 保留分类行（#genre# 和标题）
        if '#genre#' in line:
            best_sources[f'_genre_{line}'] = (line, 9999, line, '')
            continue
        
        # 保留分隔线
        if '⬇️' in line or '➡️' in line:
            best_sources[f'_sep_{line}'] = (line, 9998, line, '')
            continue
        
        # 解析行
        name, url = parse_line(line)
        if not name or not url:
            continue
        
        # 跳过无效URL
        if not url.startswith(('http', 'https', 'rtmp', 'p3p', 'P2p', 'video://')):
            stats['skipped'] += 1
            continue
        
        # 清理名称用于去重
        clean_name = clean_channel_name(name)
        if not clean_name:
            # 如果清理后为空，使用原始名称
            clean_name = name[:20]
        
        # 计算源质量分数
        score = get_source_priority(url, name)
        
        # 判断类别
        category = '其他'
        for cat, keywords in categories.items():
            if any(kw in name for kw in keywords):
                category = cat
                break
        stats['by_category'][category] += 1
        
        # 保留最优源
        if clean_name not in best_sources:
            best_sources[clean_name] = (line, score, name, url)
            stats['kept'] += 1
        else:
            existing_score = best_sources[clean_name][1]
            if score > existing_score:
                # 新源更好，替换
                old_line = best_sources[clean_name][0]
                best_sources[clean_name] = (line, score, name, url)
                stats['duplicates'] += 1
                # 被替换的也计入去重
            else:
                stats['duplicates'] += 1
    
    # 写入去重后的文件
    print(f"\n💾 写入文件: {output_file}")
    with open(output_file, 'w', encoding='utf-8') as f:
        # 写入头部信息
        f.write(f"# 精简直播源列表\n")
        f.write(f"# 生成时间: {__import__('time').strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"# 原始: {stats['total']} 行, 去重后: {len(best_sources)} 个\n")
        f.write("#genre#\n\n")
        
        # 按类别分组写入
        category_items = defaultdict(list)
        genre_items = []
        sep_items = []
        
        for key, (line, score, name, url) in best_sources.items():
            if key.startswith('_genre_'):
                genre_items.append(line)
            elif key.startswith('_sep_'):
                sep_items.append(line)
            else:
                # 判断类别
                category = '其他'
                for cat, keywords in categories.items():
                    if any(kw in name for kw in keywords):
                        category = cat
                        break
                category_items[category].append((line, score))
        
        # 写入分类标题
        f.write(f"# 央视频道 ({len(category_items['央视'])}个)\n")
        f.write("#genre#\n")
        for line, _ in sorted(category_items['央视'], key=lambda x: x[1], reverse=True):
            f.write(line + '\n')
        f.write('\n')
        
        f.write(f"# 卫视频道 ({len(category_items['卫视'])}个)\n")
        f.write("#genre#\n")
        for line, _ in sorted(category_items['卫视'], key=lambda x: x[1], reverse=True):
            f.write(line + '\n')
        f.write('\n')
        
        f.write(f"# 港澳台频道 ({len(category_items['港澳台'])}个)\n")
        f.write("#genre#\n")
        for line, _ in sorted(category_items['港澳台'], key=lambda x: x[1], reverse=True):
            f.write(line + '\n')
        f.write('\n')
        
        f.write(f"# 赛事频道 ({len(category_items['赛事'])}个)\n")
        f.write("#genre#\n")
        for line, _ in sorted(category_items['赛事'], key=lambda x: x[1], reverse=True):
            f.write(line + '\n')
        f.write('\n')
        
        f.write(f"# 新闻频道 ({len(category_items['新闻'])}个)\n")
        f.write("#genre#\n")
        for line, _ in sorted(category_items['新闻'], key=lambda x: x[1], reverse=True):
            f.write(line + '\n')
        f.write('\n')
        
        f.write(f"# 电影频道 ({len(category_items['电影'])}个)\n")
        f.write("#genre#\n")
        for line, _ in sorted(category_items['电影'], key=lambda x: x[1], reverse=True):
            f.write(line + '\n')
        f.write('\n')
        
        f.write(f"# 音乐频道 ({len(category_items['音乐'])}个)\n")
        f.write("#genre#\n")
        for line, _ in sorted(category_items['音乐'], key=lambda x: x[1], reverse=True):
            f.write(line + '\n')
        f.write('\n')
        
        f.write(f"# 其他频道 ({len(category_items['其他'])}个)\n")
        f.write("#genre#\n")
        for line, _ in sorted(category_items['其他'], key=lambda x: x[1], reverse=True):
            f.write(line + '\n')
        f.write('\n')
        
        # 写入分类线和备注
        for line in genre_items + sep_items:
            f.write(line + '\n')
    
    # 输出统计
    print("\n" + "="*60)
    print("📊 去重统计")
    print("="*60)
    print(f"总行数:        {stats['total']}")
    print(f"保留频道:      {stats['kept']}")
    print(f"去重删除:      {stats['duplicates']}")
    print(f"跳过无效:      {stats['skipped']}")
    print(f"最终频道数:    {len(best_sources)}")
    print("\n分类统计:")
    for category, count in sorted(stats['by_category'].items(), key=lambda x: x[1], reverse=True):
        print(f"  {category}: {count} 个")
    print("="*60)
    print(f"✅ 结果已保存到: {output_file}")
    
    return output_file

# 主程序入口
if __name__ == "__main__":
    import sys
    
    # 默认处理 myq.txt
    input_file = "myq.txt"
    
    # 如果命令行指定了文件
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
    
    # 检查文件是否存在
    if not os.path.exists(input_file):
        print(f"❌ 文件不存在: {input_file}")
        print("使用方法: python dedup.py [文件名]")
        print("默认文件名: myq.txt")
        sys.exit(1)
    
    # 执行去重
    output_file = deduplicate_sources(input_file)
    
    print(f"\n💡 可以使用以下命令查看结果:")
    print(f"   cat {output_file}")
    print(f"   less {output_file}")
