#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
IPTV Channel Manager - IPTV直播源管理工具
功能：自动分类、去重、按类别保存直播源
"""

import re
import os
import sys
import time
import glob
import shutil
from collections import defaultdict

# 导入正则配置
try:
    from regex_patterns import match_category
    REGEX_LOADED = True
    print("✅ 已加载正则配置文件: regex_patterns.py")
except ImportError:
    REGEX_LOADED = False
    print("⚠️ 未找到 regex_patterns.py，使用内置简单分类")
    
    # 简单备用分类
    def match_category(name):
        if re.search(r'(?i)(CCTV|cctv|央视|中央|CGTN)', name):
            return '央视'
        if re.search(r'(?i)卫视', name):
            return '卫视'
        if re.search(r'(?i)(无线|有线|Now|Viu|RTHK|凤凰|翡翠|明珠|台视|中视|华视|民视|公视|东森|纬来|三立|TVBS|八大|靖天)', name):
            return '港澳台'
        if re.search(r'(?i)(体育|赛事|NBA|英超|足球|篮球|中超|世界杯|欧冠|网球|高尔夫|F1|格斗|搏击)', name):
            return '赛事'
        if re.search(r'(?i)(新闻|资讯|新华社|澎湃)', name):
            return '新闻'
        if re.search(r'(?i)(电影|影院|美亚|HBO|AXN|龙祥|龙华|天映)', name):
            return '电影'
        if re.search(r'(?i)(音乐|歌曲|串烧|DJ|演唱会|MTV)', name):
            return '音乐'
        if re.search(r'(?i)(综艺|娱乐|喜剧|小品|相声|脱口秀)', name):
            return '综艺'
        if re.search(r'(?i)(纪录|探索|地理|动物|自然|国家地理|Discovery|BBC)', name):
            return '纪录片'
        if re.search(r'(?i)(卡通|动漫|少儿|动画|亲子|儿童|幼幼|MoMo|Nick)', name):
            return '儿童'
        if re.search(r'(?i)(财经|经济|商业|投资|股市)', name):
            return '财经'
        return '其他'


# ============================================
# 核心函数
# ============================================

def clean_channel_name(name):
    """清理频道名称，提取核心名称用于去重"""
    name = re.sub(r'\[[A-Za-z0-9|]+\]', '', name)
    name = re.sub(r'[➡️⬇️]', '', name)
    
    suffixes = ['咪咕', '高码', '4k', '4K', '欣赏', '频陆', '频晴', 
                'Mttv', 'SXtv', 'Hktv', 'FYtv', '4Gtv', '地波', 
                '广州', '高清', 'HD', '超清', 'Pdtv', 'Petv', 
                'SX', 'FY', 'Cx', 'mg', 'mv', 'Pe', '频测',
                'Web', '网页', '直播', '测试', '频道']
    for suffix in suffixes:
        name = name.replace(suffix, '')
    
    name = re.sub(r'[【】\(\)（）]', '', name)
    name = re.sub(r'[｜|]', '', name)
    name = name.strip()
    
    # CCTV
    if 'CCTV' in name or 'cctv' in name:
        match = re.search(r'(CCTV[-+]?\d+[pP]?\+?)', name, re.IGNORECASE)
        if match:
            return match.group(1).upper()
    
    # 卫视
    if '卫视' in name:
        match = re.search(r'([\u4e00-\u9fa5]+卫视)', name)
        if match:
            return match.group(1)
    
    # 港澳台特殊
    special = ['凤凰', '无线', '有线', 'Now', 'VIUTV', 'RTHK', 'TVB', 
               '翡翠', '明珠', '澳视', '澳门', '中天', '东森', '民视', 
               '台视', '中视', '华视', '三立', '纬来', '八大', '博斯', 
               'ELTA', 'HBO', 'Discovery', '国家地理']
    for s in special:
        if s in name:
            return s
    
    if len(name) > 20:
        match = re.search(r'([\u4e00-\u9fa5a-zA-Z0-9]+)', name)
        if match:
            return match.group(1)
        return name[:20]
    
    return name if name else 'unknown'


def get_source_priority(url, name):
    """评估源质量，分数越高越优"""
    score = 0
    url_lower = url.lower()
    name_lower = name.lower()
    
    if '4k' in url_lower or '4k' in name_lower:
        score += 1000
    if '.m3u8' in url_lower:
        score += 500
    if url_lower.startswith('https'):
        score += 300
    elif url_lower.startswith('http'):
        score += 200
    if '高码' in name_lower:
        score += 300
    if 'raw.githubusercontent.com' in url_lower:
        score += 150
    if 'cdn' in url_lower:
        score += 100
    if '咪咕' in name_lower:
        score += 80
    if 'test' in url_lower:
        score -= 100
    
    return score


def parse_line(line):
    """解析一行，返回 (频道名, URL)"""
    line = line.strip()
    if not line or '#genre#' in line:
        return None, None
    if ',' in line:
        parts = line.split(',', 1)
        return parts[0].strip(), parts[1].strip() if len(parts) > 1 else ''
    return None, None


def backup_file(filepath):
    """自动备份原文件"""
    if os.path.exists(filepath):
        backup_name = f"{filepath}.backup_{time.strftime('%Y%m%d_%H%M%S')}"
        shutil.copy2(filepath, backup_name)
        print(f"💾 已备份: {backup_name}")
        return backup_name
    return None


def select_file():
    """交互式选择文件"""
    txt_files = glob.glob("*.txt")
    txt_files = [f for f in txt_files if 'dedup' not in f and 'backup' not in f and 'report' not in f]
    
    if not txt_files:
        print("❌ 当前目录没有找到txt文件")
        return None
    
    print("\n📁 可用的txt文件:")
    for i, f in enumerate(txt_files, 1):
        size = os.path.getsize(f) / 1024
        print(f"  {i}. {f} ({size:.1f} KB)")
    
    print(f"  {len(txt_files) + 1}. 手动输入文件名")
    print("  0. 退出")
    
    try:
        choice = input("\n请选择文件: ").strip()
        if choice == '0':
            return None
        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(txt_files):
                return txt_files[idx]
            elif idx == len(txt_files):
                return input("请输入文件名: ").strip()
    except:
        pass
    
    return None


def deduplicate_and_split(input_file, output_dir='output'):
    """去重并按类别分别保存到不同文件"""
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    print(f"\n📂 读取文件: {input_file}")
    backup_file(input_file)
    
    with open(input_file, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
    
    print(f"📊 总行数: {len(lines)}")
    
    categories_data = defaultdict(list)
    genre_lines = []
    sep_lines = []
    
    stats = {
        'total': 0, 'kept': 0, 'duplicates': 0,
        'skipped': 0, 'invalid_urls': 0,
        'by_category': defaultdict(int)
    }
    seen_channels = defaultdict(set)
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        stats['total'] += 1
        
        if '#genre#' in line:
            genre_lines.append(line)
            continue
        if '⬇️' in line or '➡️' in line:
            sep_lines.append(line)
            continue
        
        name, url = parse_line(line)
        if not name or not url:
            stats['skipped'] += 1
            continue
        
        valid_prefixes = ('http', 'https', 'rtmp', 'p3p', 'P2p', 'video://', 'p3p://', 'P2P')
        if not url.startswith(valid_prefixes):
            stats['invalid_urls'] += 1
            continue
        
        clean_name = clean_channel_name(name)
        if not clean_name:
            clean_name = name[:20] if len(name) > 20 else name
        if not clean_name:
            continue
        
        score = get_source_priority(url, name)
        category = match_category(name)
        stats['by_category'][category] += 1
        
        if clean_name in seen_channels[category]:
            existing_score = 0
            for item in categories_data[category]:
                if item[0] == clean_name:
                    existing_score = item[2]
                    break
            if score > existing_score:
                categories_data[category] = [
                    (cn, ln, sc, u) for cn, ln, sc, u in categories_data[category] 
                    if cn != clean_name
                ]
                categories_data[category].append((clean_name, line, score, url))
                stats['duplicates'] += 1
            else:
                stats['duplicates'] += 1
        else:
            categories_data[category].append((clean_name, line, score, url))
            seen_channels[category].add(clean_name)
            stats['kept'] += 1
    
    # 保存
    saved_files = []
    categories_order = ['央视', '卫视', '港澳台', '赛事', '新闻', '电影', '音乐', '综艺', '纪录片', '儿童', '财经', '其他']
    
    for category in categories_order:
        if category not in categories_data or not categories_data[category]:
            continue
        
        filename = f"{output_dir}/{category}_{timestamp}.txt"
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(f"# {category}频道列表\n")
            f.write(f"# 更新时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"# 共 {len(categories_data[category])} 个频道\n")
            f.write("#genre#\n")
            for clean_name, line, score, url in sorted(categories_data[category], key=lambda x: x[2], reverse=True):
                f.write(line + '\n')
        
        saved_files.append((category, filename, len(categories_data[category])))
        print(f"  ✅ {category}: {len(categories_data[category])} 个 → {filename}")
    
    # 索引
    index_file = f"{output_dir}/索引_{timestamp}.txt"
    with open(index_file, 'w', encoding='utf-8') as f:
        f.write("="*50 + "\n")
        f.write("📊 IPTV直播源分类索引\n")
        f.write("="*50 + "\n")
        f.write(f"生成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"原始文件: {input_file}\n")
        f.write(f"总行数: {stats['total']}\n")
        f.write(f"有效频道: {stats['kept']}\n\n")
        f.write("各分类统计:\n")
        for category, count in sorted(stats['by_category'].items(), key=lambda x: x[1], reverse=True):
            if count > 0:
                f.write(f"  {category}: {count} 个 → {category}_{timestamp}.txt\n")
    
    saved_files.append(('索引', index_file, 1))
    
    print("\n" + "="*60)
    print("📊 处理完成")
    print("="*60)
    print(f"总行数:        {stats['total']}")
    print(f"保留频道:      {stats['kept']}")
    print(f"去重删除:      {stats['duplicates']}")
    print(f"跳过无效:      {stats['skipped']}")
    print(f"无效URL:       {stats['invalid_urls']}")
    print("\n分类统计:")
    for category, count in sorted(stats['by_category'].items(), key=lambda x: x[1], reverse=True):
        if count > 0:
            print(f"  {category}: {count} 个")
    print("="*60)
    print(f"📁 输出目录: {output_dir}")
    print(f"📄 索引文件: {index_file}")
    
    return saved_files


def main():
    """主程序"""
    print("="*60)
    print("📺 IPTV Channel Manager - IPTV直播源管理工具")
    print("="*60)
    print(f"版本: 2.0")
    print(f"正则配置: {'✅ 已加载' if REGEX_LOADED else '⚠️ 使用内置'}")
    print(f"时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
    else:
        input_file = select_file()
        if not input_file:
            print("\n已取消")
            sys.exit(0)
    
    if not os.path.exists(input_file):
        print(f"❌ 文件不存在: {input_file}")
        sys.exit(1)
    
    saved_files = deduplicate_and_split(input_file, 'output')
    
    print("\n💡 生成的文件:")
    for category, filename, count in saved_files:
        print(f"   {category}: {filename} ({count}个)")
    print("\n✅ 完成！请查看 output 目录")
    print("="*60)


if __name__ == "__main__":
    import sys
    main()
