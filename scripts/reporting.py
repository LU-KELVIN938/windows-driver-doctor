"""Offline bilingual Markdown and HTML rendering, with no remote assets."""
from __future__ import annotations

import html
import json

LABELS = {
    'en': {'title': 'Windows Driver Doctor', 'subtitle': 'Evidence first. Targeted next steps.',
           'synthetic': 'SYNTHETIC DEMO — this is not a real computer diagnosis', 'captured': 'Snapshot captured',
           'warning': 'Needs review', 'info': 'Context', 'observed': 'Observed', 'hypothesis': 'Hypothesis', 'incomplete': 'Incomplete evidence',
           'next': 'Next step', 'evidence': 'Evidence', 'inventory': 'Inventory and collection coverage',
           'comparison': 'Before / after comparison', 'limits': 'Interpretation and privacy limits',
           'limits_text': 'This is a bounded evidence summary, not a root-cause verdict. Unavailable checks are not passes. Driver dates and named crash modules do not prove a faulty driver. Redaction is best-effort: review before sharing. No system repair was performed.',
           'all': 'All findings', 'warnings': 'Needs review only', 'search': 'Search findings',
           'empty': 'No rows captured', 'ok': 'Collected', 'partial': 'Partially verified', 'not_verified': 'Not verified',
           'bounded': 'Viewer shows at most 200 rows per section; full sanitized inventory is in snapshot.json.',
           'no_comparison': 'No comparison supplied.', 'boot_note': 'Different boot records do not by themselves establish comparable boot modes.',
           'no_auto_fix': 'Read-only evidence • Local files • No automatic fix', 'print': 'Print / save PDF',
           'run': 'Run provenance', 'manifest': 'manifest.json records inputs, settings, code hash and output hashes.'},
    'zh': {'title': 'Windows 驱动诊断助手', 'subtitle': '先看证据，再给出针对性的下一步。',
           'synthetic': '模拟数据演示——不是实际电脑诊断', 'captured': '快照采集时间',
           'warning': '需要检查', 'info': '背景信息', 'observed': '已观察事实', 'hypothesis': '可能原因', 'incomplete': '证据不完整',
           'next': '下一步', 'evidence': '证据', 'inventory': '设备清单与采集覆盖情况',
           'comparison': '修复前后对比', 'limits': '判断与隐私边界',
           'limits_text': '这是有限范围的证据摘要，不是根本原因结论。未验证的检查不能算通过。驱动日期和崩溃模块名称不能证明驱动有问题。脱敏为尽力处理，分享前需检查。本次报告生成未执行系统修复。',
           'all': '全部条目', 'warnings': '只看需要检查', 'search': '搜索检查条目',
           'empty': '未采集到条目', 'ok': '已采集', 'partial': '部分验证', 'not_verified': '未验证',
           'bounded': '每个清单最多展示 200 行；完整脱敏清单见 snapshot.json。',
           'no_comparison': '没有提供前后对比数据。', 'boot_note': '不同的开机事件并不自动代表可比较的启动模式。',
           'no_auto_fix': '只读证据 · 本地文件 · 不自动修复', 'print': '打印 / 保存 PDF',
           'run': '运行来源记录', 'manifest': 'manifest.json 记录输入、设置、代码哈希和输出哈希。'}
}

SECTIONS = {
    'system': ('System and firmware', '系统与固件'), 'devices': ('PnP devices', 'PnP 设备'),
    'drivers': ('Signed-driver inventory', '签名驱动清单'), 'gpu': ('Graphics', '显卡'),
    'audio': ('Audio', '音频'), 'usb': ('USB', 'USB'), 'network': ('Network adapters', '网络适配器'),
    'disks': ('Storage health', '存储健康'), 'disk_reliability': ('Storage reliability counters', '存储可靠性计数器'),
    'battery': ('Battery', '电池'), 'resource': ('Current resource snapshot', '当前资源快照'),
    'startup': ('Startup registrations', '启动项注册'), 'services': ('Automatic services', '自动服务'),
    'tasks': ('Boot / logon tasks', '开机 / 登录任务'), 'events': ('Event timeline', '事件时间线'),
    'driver_events': ('Device configuration timeline', '设备配置时间线'),
    'boot': ('Boot measurements', '开机观测'), 'boot_components': ('Boot components', '开机组件'),
    'dumps': ('Dump metadata only', '仅转储文件元数据'), 'security': ('Security context', '安全上下文'),
    'volumes': ('Local volume space', '本地磁盘空间'), 'battery_health': ('Battery capacity evidence', '电池容量证据'),
    'updates': ('Update and reboot context', '更新与重启上下文')
}

ZH_FIELDS = {'name': '名称', 'class': '类别', 'present': '已连接', 'problem_code': '故障代码', 'status': '状态',
             'version': '版本', 'provider': '提供程序', 'date': '日期', 'inf': 'INF', 'signed': '已签名',
             'device_name': '设备名称', 'device_key': '设备代号', 'driver_file': '驱动文件', 'time': '时间',
             'id': '事件编号', 'record_id': '记录编号', 'log': '日志', 'level': '级别', 'bugcheck_code': '蓝屏代码',
             'data': '数据', 'health': '健康状态', 'operational': '运行状态', 'bytes': '字节数',
             'manufacturer': '制造商', 'model': '型号', 'bios_version': 'BIOS 版本', 'bios_date': 'BIOS 日期',
             'last_boot': '最近启动', 'total_memory_kb': '总内存 KB', 'free_memory_kb': '可用内存 KB',
             'commit_percent': '提交内存百分比', 'cpu_percent': 'CPU 百分比', 'charge_percent': '电量百分比',
             'description': '说明', 'source': '来源', 'state': '状态', 'start_mode': '启动方式', 'location': '位置',
             'triggers': '触发器', 'boot_ms': '开机毫秒', 'main_path_ms': '主路径毫秒', 'post_boot_ms': '桌面后毫秒',
             'duration_ms': '耗时毫秒', 'degradation_ms': '延迟毫秒', 'kind': '类型', 'modified': '修改时间',
             'friendly_name': '显示名称', 'temperature': '温度', 'wear': '损耗', 'power_on_hours': '通电小时',
             'change': '变化', 'before': '之前', 'after': '之后', 'delta_seconds': '差值秒',
             'before_seconds': '之前秒', 'after_seconds': '之后秒', 'note': '说明', 'os': '系统', 'build': '构建号'}


def display(value, lang='en'):
    if value is None:
        return 'Not available' if lang == 'en' else '不可用'
    if value is True:
        return 'Yes' if lang == 'en' else '是'
    if value is False:
        return 'No' if lang == 'en' else '否'
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, indent=2)
    return str(value)


def table(items, lang):
    if not items:
        return '<p class="muted">' + LABELS[lang]['empty'] + '</p>'
    keys = list(dict.fromkeys(k for row in items[:200] for k in row))
    heading = ''.join('<th>' + html.escape(ZH_FIELDS.get(k, k) if lang == 'zh' else k.replace('_', ' ').capitalize()) + '</th>' for k in keys)
    body = ''.join('<tr>' + ''.join('<td>' + html.escape(display(row.get(k), lang)) + '</td>' for k in keys) + '</tr>' for row in items[:200])
    return '<div class="table-wrap"><table><thead><tr>' + heading + '</tr></thead><tbody>' + body + '</tbody></table></div>'


def pane(report, lang):
    labels = LABELS[lang]
    escape = html.escape
    bits = []
    if report.get('synthetic'):
        bits.append('<div class="demo">' + labels['synthetic'] + '</div>')
    bits.append('<header><p class="eyebrow">' + labels['no_auto_fix'] + '</p><h1>' + labels['title'] + '</h1><p>' + labels['subtitle'] + '</p><p class="muted">' + labels['captured'] + ': ' + escape(str(report.get('captured_at') or '—')) + '</p></header>')
    counts = {s: sum(f['severity'] == s for f in report['findings']) for s in ('warning', 'info')}
    bits.append('<div class="stats"><div><b>' + str(counts['warning']) + '</b>' + labels['warning'] + '</div><div><b>' + str(counts['info']) + '</b>' + labels['info'] + '</div></div>')
    bits.append('<div class="filters"><select class="severity-filter" aria-label="' + labels['all'] + '"><option value="all">' + labels['all'] + '</option><option value="warning">' + labels['warnings'] + '</option></select><input class="search" placeholder="' + labels['search'] + '" aria-label="' + labels['search'] + '"></div>')
    for item in report['findings']:
        bits.append('<article class="finding ' + item['severity'] + '" data-severity="' + item['severity'] + '"><div class="badges"><span>' + labels[item['severity']] + '</span><span>' + labels[item['confidence']] + '</span></div><h2>' + escape(item['title'][lang]) + '</h2><p>' + escape(item['detail'][lang]) + '</p><p><strong>' + labels['next'] + ':</strong> ' + escape(item['next_step'][lang]) + '</p>')
        if item.get('evidence'):
            bits.append('<details><summary>' + labels['evidence'] + '</summary><pre>' + escape(json.dumps(item['evidence'], ensure_ascii=False, indent=2)) + '</pre></details>')
        bits.append('</article>')
    comparison = report.get('comparison')
    if comparison is not None:
        bits.append('<section class="panel"><h2>' + labels['comparison'] + '</h2>')
        for field, title in [('driver_changes', ('Driver changes', '驱动变化')), ('device_changes', ('Device changes', '设备变化')), ('new_events', ('New captured events', '新增事件'))]:
            bits.append('<details><summary>' + title[lang == 'zh'] + ' (' + str(len(comparison[field])) + ')</summary>' + table(comparison[field], lang) + '</details>')
        bits.append('<p>' + labels['boot_note'] + '</p><pre>' + escape(json.dumps(comparison['boot'], ensure_ascii=False, indent=2)) + '</pre>')
        if comparison.get('unavailable'):
            bits.append('<p class="muted">' + labels['not_verified'] + ': ' + escape(', '.join(comparison['unavailable'])) + '</p>')
        bits.append('</section>')
    bits.append('<section class="panel"><h2>' + labels['inventory'] + '</h2><p class="muted">' + labels['bounded'] + '</p>')
    for name, section in report['sections'].items():
        title = SECTIONS.get(name, (name, name))[lang == 'zh']
        bits.append('<details><summary>' + escape(title) + ' <span class="coverage">' + labels[section['status']] + ' · ' + str(len(section['data'])) + '</span></summary>')
        if section.get('reason'):
            bits.append('<p class="muted">' + escape(str(section['reason'])) + '</p>')
        bits.append(table(section['data'], lang) + '</details>')
    bits.append('</section><footer><h2>' + labels['limits'] + '</h2><p>' + labels['limits_text'] + '</p><h3>' + labels['run'] + '</h3><p>' + labels['manifest'] + '</p></footer>')
    return ''.join(bits)


def render_html(report, lang='en'):
    # User evidence is rendered only as escaped text. No raw JSON inside scripts.
    css = """
    :root{color-scheme:light;--ink:#192c3a;--muted:#536a7a;--line:#dbe5ec;--accent:#126f69}
    *{box-sizing:border-box}body{margin:0;background:#f3f7fa;color:var(--ink);font:16px/1.6 system-ui,'Segoe UI','Microsoft YaHei',sans-serif}
    main{max-width:1160px;margin:auto;padding:28px}nav{display:flex;justify-content:flex-end;gap:8px;max-width:1160px;margin:auto;padding:22px 28px 0}
    button,select,input{font:inherit;border:1px solid var(--line);border-radius:8px;padding:8px 12px;background:white;color:var(--ink)}button{cursor:pointer}button[aria-pressed=true]{background:var(--accent);color:white}
    h1{font-size:clamp(28px,4vw,44px);line-height:1.2;letter-spacing:-1px;margin:8px 0}h2{font-size:20px;margin:12px 0}h3{font-size:17px}
    header{padding:20px 0}.eyebrow{color:var(--accent);font-size:13px;font-weight:700}.muted{color:var(--muted);font-size:14px}
    .stats{display:flex;gap:14px;margin:12px 0 22px}.stats div{display:flex;align-items:center;gap:16px;background:white;border:1px solid var(--line);border-radius:12px;padding:15px 24px}.stats b{font-size:28px}
    .filters{display:flex;gap:12px;margin-bottom:18px}.search{flex:1}.finding,.panel{border:1px solid var(--line);border-radius:12px;background:white;padding:22px;margin:16px 0}.finding.warning{border-left:5px solid #b66e13}
    .badges{display:flex;gap:8px;font-size:12px}.badges span{border-radius:5px;background:#edf3f7;padding:3px 8px}.warning .badges span:first-child{background:#fff1d8;color:#80500d}
    details{border-top:1px solid var(--line);padding-top:10px;margin-top:14px}summary{cursor:pointer;font-weight:600;padding:4px 0}.coverage{font-size:12px;color:var(--muted);font-weight:400;float:right}
    pre{white-space:pre-wrap;overflow-wrap:anywhere;max-height:500px;overflow:auto;background:#f4f7fa;border-radius:8px;padding:15px;font:12px/1.6 ui-monospace,Consolas,monospace}
    .table-wrap{overflow:auto}table{border-collapse:collapse;width:100%;font-size:12px}th,td{padding:10px;text-align:left;border-bottom:1px solid var(--line);vertical-align:top;min-width:80px;overflow-wrap:anywhere;max-width:360px;white-space:pre-wrap}th{background:#f5f8fa;position:sticky;top:0}
    footer{font-size:14px;color:var(--muted);padding:24px 0}.demo{background:#fff0d4;border:1px solid #e5c582;border-radius:8px;padding:12px;font-weight:700}.pane[hidden]{display:none!important}
    @media(max-width:650px){main{padding:16px}nav{padding:15px}.filters{flex-direction:column}.stats div{padding:12px}.coverage{float:none;display:block}.finding,.panel{padding:16px}}
    @media print{nav,.filters{display:none}body{background:white}main{max-width:none;padding:0}.finding{break-inside:avoid}.panel{border:none}details{display:block}details>*{display:block}pre{max-height:none;overflow:visible}.table-wrap{overflow:visible}.finding[hidden]{display:none!important}}
    """
    script = """
    const panes=document.querySelectorAll('.pane');
    document.querySelectorAll('[data-language]').forEach(button=>button.addEventListener('click',()=>{
      const lang=button.dataset.language;document.documentElement.lang=lang==='zh'?'zh-CN':'en';
      panes.forEach(pane=>pane.hidden=pane.dataset.lang!==lang);
      document.querySelectorAll('[data-language]').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));
    }));
    panes.forEach(pane=>{
      const select=pane.querySelector('.severity-filter'),search=pane.querySelector('.search');
      const filter=()=>pane.querySelectorAll('.finding').forEach(card=>{
        card.hidden=(select.value!=='all'&&card.dataset.severity!==select.value)||!card.textContent.toLowerCase().includes(search.value.toLowerCase());
      });select.addEventListener('change',filter);search.addEventListener('input',filter);
    });document.getElementById('print').addEventListener('click',()=>window.print());
    """
    nav = '<nav aria-label="Report controls"><button data-language="en" aria-pressed="' + str(lang == 'en').lower() + '">English</button><button data-language="zh" aria-pressed="' + str(lang == 'zh').lower() + '">简体中文</button><button id="print">Print / 打印</button></nav>'
    bodies = ''.join('<div class="pane" data-lang="' + locale + '"' + (' hidden' if locale != lang else '') + '>' + pane(report, locale) + '</div>' for locale in ('en', 'zh'))
    return '<!doctype html><html lang="' + ('zh-CN' if lang == 'zh' else 'en') + '"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Windows Driver Doctor</title><style>' + css + '</style></head><body>' + nav + '<main>' + bodies + '</main><script>' + script + '</script></body></html>'


def render_markdown(report, lang='en'):
    labels = LABELS[lang]
    lines = ['# ' + labels['title'], '']
    if report.get('synthetic'):
        lines += ['**' + labels['synthetic'] + '**', '']
    lines += [labels['captured'] + ': ' + str(report.get('captured_at') or '—'), '', labels['no_auto_fix'], '']
    for item in report['findings']:
        lines += ['## ' + item['title'][lang], '', labels[item['severity']] + ' · ' + labels[item['confidence']], '',
                  item['detail'][lang], '', '**' + labels['next'] + ':** ' + item['next_step'][lang], '']
        if item.get('evidence'):
            # Longer evidence stays in JSON/HTML, avoiding oversized chat reports.
            lines += [labels['evidence'] + ': findings.json → ' + item['id'], '']
    if report.get('comparison') is not None:
        lines += ['## ' + labels['comparison'], '', '```json', json.dumps(report['comparison'], ensure_ascii=False, indent=2), '```', '']
    lines += ['## ' + labels['inventory'], '']
    for name, section in report['sections'].items():
        title = SECTIONS.get(name, (name, name))[lang == 'zh']
        lines.append('- ' + title + ': ' + labels[section['status']] + ' (' + str(len(section['data'])) + ')')
    lines += ['', '## ' + labels['limits'], '', labels['limits_text'], '', labels['manifest'], '']
    return '\n'.join(lines)
