#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import os
import sys
import time
import glob
import shutil
from collections import defaultdict

def clean_channel_name(name):
    """清理频道名称，提取核心名称用于去重"""
    name = re.sub(r'\[[A-Za-z0-9|]+\]', '', name)
    name = re.sub(r'[➡️⬇️]', '', name)
    
    suffixes = ['咪咕', '高码', '4k', '4K', '欣赏', '频陆', '频晴', 
                'Mttv', 'SXtv', 'Hktv', 'FYtv', '4Gtv', '地波', 
                '广州', '高清', 'HD', '超清', 'Pdtv', 'Petv', 
                'SX', 'FY', 'Cx', 'mg', 'mv', 'Pe', '频测',
                'Web', '网页', '直播', '测试']
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
    
    # 港澳台特殊频道
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
    """评估源质量"""
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
    """解析一行"""
    line = line.strip()
    if not line or '#genre#' in line:
        return None, None
    if ',' in line:
        parts = line.split(',', 1)
        return parts[0].strip(), parts[1].strip() if len(parts) > 1 else ''
    return None, None

def match_hk_mo_tw_channel(name):
    """使用正则匹配港澳台频道"""
    hk_patterns = {
        '凤凰卫视': r'(凤凰卫视|凤凰中文|凤凰资讯|凤凰香港|凤凰电影)',
        '翡翠台': r'(翡翠台|无线翡翠|华丽翡翠|高清翡翠|翡翠综合|翡翠剧集|翡翠娱乐|黄金翡翠)',
        '明珠台': r'(明珠台|无线明珠)',
        '无线新闻': r'(无线新闻|无线财经资讯|无线娱乐新闻)',
        '无线剧集': r'(无线剧集|无线经典|无线音乐|无线生活|无线功夫|无线星河)',
        '无线儿童': r'(无线儿童|无线娱乐)',
        'Now TV': r'(Now新闻|Now财经|Now爆谷|Now星影|Now英超|Now体育|Now直播|Now华语|Now)',
        'ViuTV': r'(ViuTV|VIUTV|ViuTV6)',
        'HOY TV': r'(HOY TV|HOY 77|HOY 78|HOY资讯|HOY财经|HOY)',
        '港台电视': r'(港台电视31|港台电视32|港台电视33|港台电视34|港台电视35|RTHK)',
        '有线电视': r'(有线新闻|有线综合|有线赛马|有线体育)',
        '美亚电影': r'(美亚电影|美亚电视|美亚娱乐)',
        '星空卫视': r'(星空卫视|星空电影|星空音乐)',
        'TVB': r'(TVBJ1|TVBJ2|TVB Plus|TVBS|TVB)',
        '香港开电视': r'(香港开电视|开电视)',
        '香港财经台': r'(香港财经台|财经台)',
        'PopC电影': r'(PopC电影|pₒₚc电影)',
        '千禧经典台': r'(千禧经典|千禧台|经典台)',
        '华语剧台': r'(华语剧台|亚洲剧台|剧集台)',
    }
    
    mo_patterns = {
        '澳视澳门': r'(澳视澳门|澳门卫视)',
        '澳视卫星': r'(澳视卫星|卫星台)',
        '澳视葡文': r'(澳视葡文|葡文台)',
        '澳门资讯': r'(澳门资讯|资讯台)',
        '澳门体育': r'(澳门体育|体育台)',
        '澳门综艺': r'(澳门综艺|综艺台)',
        '澳门莲花': r'(澳门莲花|莲花卫视|莲花台)',
        '澳门卫星': r'(澳门卫星|卫星电视)',
    }
    
    tw_patterns = {
        '台视': r'(台视|TTV|台湾电视)',
        '中视': r'(中视|CTV|中国电视)',
        '华视': r'(华视|CTS|中华电视)',
        '民视': r'(民视|FTV|民间电视)',
        '公视': r'(公视|PTS|公共电视)',
        '台视新闻': r'(台视新闻|TTV News)',
        '中视新闻': r'(中视新闻|CTV News)',
        '华视新闻': r'(华视新闻|CTS News)',
        '民视新闻': r'(民视新闻|FTV News)',
        '公视新闻': r'(公视新闻|PTS News)',
        '三立新闻': r'(三立新闻|SET News)',
        'TVBS新闻': r'(TVBS新闻|TVBS-N)',
        '东森新闻': r'(东森新闻|EBC News)',
        '中天新闻': r'(中天新闻|CTi News)',
        '寰宇新闻': r'(寰宇新闻|Global News)',
        '非凡新闻': r'(非凡新闻|Unique News)',
        '年代新闻': r'(年代新闻|Era News)',
        '壹电视新闻': r'(壹电视新闻|Next TV News)',
        '东森综合': r'(东森综合|EBC综合)',
        '东森戏剧': r'(东森戏剧|EBC戏剧)',
        '东森洋片': r'(东森洋片|EBC洋片)',
        '东森幼幼': r'(东森幼幼|EBC YOYO)',
        '东森财经': r'(东森财经|EBC财经)',
        '东森电影': r'(东森电影|EBC电影)',
        '纬来综合': r'(纬来综合|VL综合)',
        '纬来戏剧': r'(纬来戏剧|VL戏剧)',
        '纬来日本': r'(纬来日本|VL Japan)',
        '纬来育乐': r'(纬来育乐|VL育乐)',
        '纬来体育': r'(纬来体育|VL体育)',
        '纬来电影': r'(纬来电影|VL电影)',
        '纬来精彩': r'(纬来精彩|VL精彩)',
        '三立台湾': r'(三立台湾|SET台湾)',
        '三立综合': r'(三立综合|SET综合)',
        '三立都会': r'(三立都会|SET都会)',
        '三立戏剧': r'(三立戏剧|SET戏剧)',
        'TVBS欢乐': r'(TVBS欢乐|TVBS欢乐台)',
        'TVBS精彩': r'(TVBS精彩|TVBS精彩台)',
        '八大综合': r'(八大综合|GTV综合)',
        '八大戏剧': r'(八大戏剧|GTV戏剧)',
        '八大娱乐': r'(八大娱乐|GTV娱乐)',
        '龙祥电影': r'(龙祥电影|LS TIME)',
        '龙华电影': r'(龙华电影|龙华戏剧|龙华经典|龙华偶像|龙华日韩|龙华洋片|龙华卡通)',
        '好莱坞电影': r'(好莱坞电影|Hollywood)',
        'HBO': r'(HBO|HBO家庭|HBO强档|HBO原创|HBO Signature)',
        'AXN': r'(AXN|AXN频道)',
        'CINEMAX': r'(CINEMAX|Cine Max)',
        'Star Movies': r'(Star Movies|卫视电影)',
        '天映经典': r'(天映经典|天映频道|天映卡通)',
        'tvN': r'(tvN|韩剧台)',
        '博斯运动': r'(博斯运动|博斯网球|博斯高球|博斯魅力|博斯无限)',
        '爱尔达体育': r'(爱尔达体育|ELTA体育|ELTA)',
        'MoMo亲子': r'(MoMo亲子|MOMO亲子)',
        '卡通频道': r'(卡通频道|Cartoon Network)',
        '尼克卡通': r'(尼克卡通|Nickelodeon|Nick)',
        'Animax': r'(Animax|动漫台)',
        '大爱电视': r'(大爱电视|大爱一台|大爱二台)',
        '好消息卫视': r'(好消息卫视|GOOD TV)',
        '人间卫视': r'(人间卫视|Life TV)',
        '客家电视台': r'(客家电视台|Hakka TV)',
        '原住民电视台': r'(原住民族电视|TITV)',
        'TaiwanPlus': r'(TaiwanPlus|台湾\+)',
        'astro': r'(astro|Astro|AOD|AEC|欢喜|爱奇艺|QJ)',
        '八度空间': r'(八度空间|8TV)',
        'Channel': r'(Channel [85U]|Channel)',
    }
    
    all_patterns = {**hk_patterns, **mo_patterns, **tw_patterns}
    
    for standard_name, pattern in all_patterns.items():
        if re.search(pattern, name, re.IGNORECASE):
            return standard_name
    return None

def categorize_channel(name, url=''):
    """综合判断频道类别"""
    
    # 1. 港澳台
    if match_hk_mo_tw_channel(name):
        return '港澳台'
    
    # 2. 央视
    if re.search(r'(CCTV|cctv|央视|中央|CGTN)', name):
        return '央视'
    
    # 3. 卫视
    if re.search(r'([\u4e00-\u9fa5]+卫视)', name):
        return '卫视'
    
    # 4. 赛事
    if re.search(r'(体育|赛事|NBA|英超|足球|篮球|中超|世界杯|欧冠|网球|高尔夫|F1|格斗|搏击|拳击|赛马)', name):
        return '赛事'
    
    # 5. 新闻
    if re.search(r'(新闻|资讯|新华社|澎湃)', name):
        return '新闻'
    
    # 6. 电影
    if re.search(r'(电影|影院|大片|影厅|剧场|院线|美亚|HBO|AXN)', name):
        return '电影'
    
    # 7. 音乐
    if re.search(r'(音乐|歌曲|串烧|DJ|演唱会|MTV)', name):
        return '音乐'
    
    # 8. 综艺
    if re.search(r'(综艺|娱乐|明星|喜剧|小品|相声|脱口秀)', name):
        return '综艺'
    
    # 9. 纪录片
    if re.search(r'(纪录|探索|地理|动物|自然|国家地理|Discovery|BBC)', name):
        return '纪录片'
    
    # 10. 儿童
    if re.search(r'(卡通|动漫|少儿|动画|亲子|儿童|幼幼|MoMo|Nick)', name):
        return '儿童'
    
    # 11. 财经
    if re.search(r'(财经|经济|商业|投资|股市)', name):
        return '财经'
    
    return '其他'

def deduplicate_and_split(input_file, output_dir='output'):
    """
    去重并按类别分别保存到不同文件
    """
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    
    # 创建输出目录
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    print(f"📂 读取文件: {input_file}")
    
    with open(input_file, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
    
    print(f"📊 总行数: {len(lines)}")
    
    # 存储各类别数据
    categories_data = defaultdict(list)
    genre_lines = []
    sep_lines = []
    
    stats = {
        'total': 0,
        'kept': 0,
        'duplicates': 0,
        'skipped': 0,
        'invalid_urls': 0,
        'by_category': defaultdict(int)
    }
    
    # 用于去重
    seen_channels = defaultdict(set)
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        stats['total'] += 1
        
        # 保留分类行
        if '#genre#' in line:
            genre_lines.append(line)
            continue
        
        # 保留分隔线
        if '⬇️' in line or '➡️' in line:
            sep_lines.append(line)
            continue
        
        # 解析
        name, url = parse_line(line)
        if not name or not url:
            stats['skipped'] += 1
            continue
        
        if not url.startswith(('http', 'https', 'rtmp', 'p3p', 'P2p', 'video://', 'p3p://')):
            stats['invalid_urls'] += 1
            continue
        
        # 清理名称
        clean_name = clean_channel_name(name)
        if not clean_name:
            clean_name = name[:20] if len(name) > 20 else name
        if not clean_name:
            continue
        
        # 计算质量
        score = get_source_priority(url, name)
        
        # 判断类别
        category = categorize_channel(name, url)
        stats['by_category'][category] += 1
        
        # 去重（每个类别内去重）
        if clean_name in seen_channels[category]:
            # 检查是否质量更高
            existing_score = 0
            for item in categories_data[category]:
                if item[0] == clean_name:
                    existing_score = item[2]
                    break
            if score > existing_score:
                # 替换
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
    
    # 保存每个类别到单独文件
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
            
            # 按质量排序
            for clean_name, line, score, url in sorted(categories_data[category], key=lambda x: x[2], reverse=True):
                f.write(line + '\n')
        
        saved_files.append((category, filename, len(categories_data[category])))
        print(f"  ✅ {category}: {len(categories_data[category])} 个 → {filename}")
    
    # 保存分类行和分隔线到单独文件
    if genre_lines or sep_lines:
        filename = f"{output_dir}/headers_{timestamp}.txt"
        with open(filename, 'w', encoding='utf-8') as f:
            for line in genre_lines:
                f.write(line + '\n')
            f.write('\n')
            for line in sep_lines:
                f.write(line + '\n')
        saved_files.append(('分类行', filename, len(genre_lines) + len(sep_lines)))
    
    # 保存汇总索引
    index_file = f"{output_dir}/索引_{timestamp}.txt"
    with open(index_file, 'w', encoding='utf-8') as f:
        f.write("="*50 + "\n")
        f.write("📊 直播源分类索引\n")
        f.write("="*50 + "\n")
        f.write(f"生成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"原始文件: {input_file}\n")
        f.write(f"总行数: {stats['total']}\n")
        f.write(f"有效频道: {stats['kept']}\n\n")
        f.write("各分类统计:\n")
        for category, count in sorted(stats['by_category'].items(), key=lambda x: x[1], reverse=True):
            if count > 0:
                filename = f"{category}_{timestamp}.txt"
                f.write(f"  {category}: {count} 个 → {filename}\n")
        f.write("\n" + "="*50 + "\n")
        f.write("使用方法:\n")
        f.write("  将需要的分类文件添加到播放器即可\n")
    
    saved_files.append(('索引', index_file, 1))
    
    # 统计
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

if __name__ == "__main__":
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
