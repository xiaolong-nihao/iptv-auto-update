#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import os
from collections import defaultdict
import sys
import time

def clean_channel_name(name):
    """
    清理频道名称，提取核心名称用于去重
    """
    # 1. 删除方括号标签 [Pd] [Mt] [Hk] 等
    name = re.sub(r'\[[A-Za-z0-9|]+\]', '', name)
    
    # 2. 删除箭头符号
    name = re.sub(r'[➡️⬇️]', '', name)
    
    # 3. 删除常见后缀
    suffixes = [
        '咪咕', '高码', '4k', '4K', '欣赏', '频陆', '频晴', 
        'Mttv', 'SXtv', 'Hktv', 'FYtv', '4Gtv', '地波', 
        '广州', '高清', 'HD', '超清', '超', '欣赏',
        'Pdtv', 'Petv', 'SX', 'FY', 'Cx', 'mg', 'mv', 'Pe',
        '频测', 'Web', '网页', '直播', '频道',
        '频陆', '频晴', '地波', '高码', '测试'
    ]
    for suffix in suffixes:
        name = name.replace(suffix, '')
    
    # 4. 删除特殊符号
    name = re.sub(r'[【】\(\)（）]', '', name)
    name = re.sub(r'[｜|]', '', name)
    name = name.strip()
    
    # 5. 特殊处理：CCTV频道
    if 'CCTV' in name or 'cctv' in name:
        # 匹配 CCTV-1, CCTV-5+, CCTV-5+咪咕 等
        match = re.search(r'(CCTV[-+]?\d+[pP]?\+?)', name, re.IGNORECASE)
        if match:
            return match.group(1).upper()
        # 匹配 CGTN
        match = re.search(r'(CGTN[-]?[a-zA-Z]*)', name, re.IGNORECASE)
        if match:
            return match.group(1)
    
    # 6. 处理卫视
    if '卫视' in name:
        match = re.search(r'([\u4e00-\u9fa5]+卫视)', name)
        if match:
            return match.group(1)
    
    # 7. 处理港澳台特色频道
    special_channels = {
        '凤凰': '凤凰',
        '无线': '无线',
        '有线': '有线',
        'Now': 'Now',
        'VIUTV': 'VIUTV',
        'RTHK': 'RTHK',
        'TVB': 'TVB',
        '翡翠': '翡翠',
        '明珠': '明珠',
        '澳视': '澳视',
        '澳门': '澳门',
        '中天': '中天',
        '东森': '东森',
        '民视': '民视',
        '台视': '台视',
        '中视': '中视',
        '华视': '华视',
        '三立': '三立',
        '纬来': '纬来',
        '八大': '八大',
        '博斯': '博斯',
        'ELTA': 'ELTA',
        'HBO': 'HBO',
        'Discovery': 'Discovery',
        '国家地理': '国家地理',
        '历史频道': '历史频道',
    }
    for key, value in special_channels.items():
        if key in name:
            return value
    
    # 8. 如果名称仍然太长，截取前20个字符
    if len(name) > 20:
        # 尝试提取有效名称
        match = re.search(r'([\u4e00-\u9fa5a-zA-Z0-9]+)', name)
        if match:
            return match.group(1)
        return name[:20]
    
    return name if name else 'unknown'

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
    
    # 5. 域名稳定性
    stable_domains = [
        'raw.githubusercontent.com', 
        'github.com',
        'cdn',
        'gitee.com',
        'net',
        'com'
    ]
    for domain in stable_domains:
        if domain in url_lower:
            score += 150
            break
    
    # 6. 不是测试源
    if 'test' in url_lower:
        score -= 100
    
    # 7. 咪咕源（通常较稳定）
    if '咪咕' in name_lower:
        score += 80
    
    # 8. 有完整路径
    if '/' in url and len(url.split('/')) > 3:
        score += 50
    
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
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        output_file = f"{base}_dedup_{timestamp}{ext}"
    
    print(f"📂 读取文件: {input_file}")
    
    if not os.path.exists(input_file):
        print(f"❌ 文件不存在: {input_file}")
        return None
    
    with open(input_file, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
    
    print(f"📊 总行数: {len(lines)}")
    
    # 存储最优源
    best_sources = {}
    stats = {
        'total': 0,
        'skipped': 0,
        'kept': 0,
        'duplicates': 0,
        'by_category': defaultdict(int),
        'invalid_urls': 0
    }
    
    # 类别关键词（扩展）
    categories = {
        '央视': ['CCTV', '央视', '中央', 'CGTN'],
        '卫视': ['卫视', '东方', '湖南', '浙江', '江苏', '北京', '深圳', 
                '广东', '天津', '山东', '四川', '河南', '辽宁', '安徽', 
                '福建', '江西', '重庆', '黑龙江', '吉林', '河北', '山西',
                '云南', '贵州', '甘肃', '青海', '宁夏', '新疆', '西藏',
                '海南', '广西', '内蒙古', '陕西', '东南卫视', '厦门卫视'],
        '港澳台': ['凤凰', 'TVB', '翡翠', '明珠', '香港', '澳门', '台湾',
                  '无线', '有线', 'Now', 'VIUTV', 'RTHK', '澳视', '莲花',
                  '中天', '东森', '民视', '台视', '中视', '华视', '三立',
                  '纬来', '八大', '博斯', 'ELTA', 'HBO', 'Discovery',
                  '国家地理', '历史频道'],
        '赛事': ['体育', '赛事', 'NBA', '英超', '足球', '篮球', '中超',
                '世界杯', '欧冠', '网球', '高尔夫', 'F1', '格斗', '搏击',
                '拳击', '电竞', '博斯', 'ELTA'],
        '新闻': ['新闻', '资讯', '新华社', '澎湃', '凤凰资讯'],
        '电影': ['电影', '影院', '大片', '影厅', '剧场'],
        '音乐': ['音乐', '歌曲', '串烧', 'DJ', '演唱会', 'MTV', 'band'],
        '综艺': ['综艺', '娱乐', '明星', '喜剧', '小品', '相声', '脱口秀'],
        '纪录片': ['纪录', '探索', '地理', '动物', '自然', '历史'],
        '儿童': ['卡通', '动漫', '少儿', '动画', '亲子'],
        '其他': []
    }
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        stats['total'] += 1
        
        # 保留分类行
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
            stats['skipped'] += 1
            continue
        
        # 检查URL是否有效
        if not url.startswith(('http', 'https', 'rtmp', 'p3p', 'P2p', 'video://', 'p3p://')):
            stats['invalid_urls'] += 1
            continue
        
        # 清理名称
        clean_name = clean_channel_name(name)
        if not clean_name:
            clean_name = name[:20] if len(name) > 20 else name
        if not clean_name:
            continue
        
        # 计算源质量分数
        score = get_source_priority(url, name)
        
        # 判断类别
        category = '其他'
        for cat, keywords in categories.items():
            if cat == '其他':
                continue
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
                best_sources[clean_name] = (line, score, name, url)
                stats['duplicates'] += 1
            else:
                stats['duplicates'] += 1
    
    # 写入文件
    print(f"\n💾 写入文件: {output_file}")
    
    with open(output_file, 'w', encoding='utf-8') as f:
        # 头部信息
        f.write(f"# 精简直播源列表\n")
        f.write(f"# 生成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"# 原始: {stats['total']} 行, 去重后: {len(best_sources)} 个频道\n")
        f.write("#genre#\n\n")
        
        # 分类
        category_items = defaultdict(list)
        genre_items = []
        sep_items = []
        
        for key, (line, score, name, url) in best_sources.items():
            if key.startswith('_genre_'):
                genre_items.append(line)
            elif key.startswith('_sep_'):
                sep_items.append(line)
            else:
                category = '其他'
                for cat, keywords in categories.items():
                    if cat == '其他':
                        continue
                    if any(kw in name for kw in keywords):
                        category = cat
                        break
                category_items[category].append((line, score))
        
        # 写入各分类
        categories_order = ['央视', '卫视', '港澳台', '赛事', '新闻', '电影', '音乐', '综艺', '纪录片', '儿童', '其他']
        for cat in categories_order:
            if cat in category_items and category_items[cat]:
                f.write(f"# {cat}频道 ({len(category_items[cat])}个)\n")
                f.write("#genre#\n")
                for line, _ in sorted(category_items[cat], key=lambda x: x[1], reverse=True):
                    f.write(line + '\n')
                f.write('\n')
        
        # 写入分类线和备注
        for line in genre_items + sep_items:
            f.write(line + '\n')
    
    # 统计信息
    print("\n" + "="*60)
    print("📊 去重统计")
    print("="*60)
    print(f"总行数:        {stats['total']}")
    print(f"保留频道:      {stats['kept']}")
    print(f"去重删除:      {stats['duplicates']}")
    print(f"跳过无效:      {stats['skipped']}")
    print(f"无效URL:       {stats['invalid_urls']}")
    print(f"最终频道数:    {len(best_sources)}")
    print("\n分类统计:")
    for category, count in sorted(stats['by_category'].items(), key=lambda x: x[1], reverse=True):
        if count > 0:
            print(f"  {category}: {count} 个")
    print("="*60)
    print(f"✅ 结果已保存到: {output_file}")
    
    return output_file

# 主程序
if __name__ == "__main__":
    # 默认文件
    input_file = "myq.txt"
    
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
    
    if not os.path.exists(input_file):
        print(f"❌ 文件不存在: {input_file}")
        print("使用方法: python dedup.py [文件名]")
        print("示例: python dedup.py myq.txt")
        sys.exit(1)
    
    output_file = deduplicate_sources(input_file)
    
    if output_file:
        print(f"\n💡 查看结果:")
        print(f"   cat {output_file}")
        print(f"   less {output_file}")
        print(f"   head -50 {output_file}")
