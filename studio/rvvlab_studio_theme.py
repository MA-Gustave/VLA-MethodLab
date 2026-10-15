"""RVV-VLA Studio visual system: structure, not an extra test engine."""
from tkinter import ttk

COLORS = {
    'bg':'#F4F7FB', 'surface':'#FFFFFF', 'ink':'#132238',
    'muted':'#63748A', 'line':'#E1E8F0', 'accent':'#155EBA',
    'light_blue':'#EAF3FF', 'ok':'#167246', 'ok_bg':'#E4F7EB',
    'active':'#8B5B00', 'active_bg':'#FFF2CF',
    'bad':'#AA2430', 'bad_bg':'#FDECEF', 'unknown':'#596B7D',
}


def apply_theme(root):
    root.configure(background=COLORS['bg'])
    style=ttk.Style(root)
    # Clam respects the cross-platform background configuration for widgets;
    # no user OS/theme preference changes are made outside this process.
    if 'clam' in style.theme_names():
        style.theme_use('clam')
    style.configure('App.TFrame',background=COLORS['bg'])
    style.configure('Surface.TFrame',background=COLORS['surface'])
    style.configure('TFrame',background=COLORS['surface'])
    style.configure('TLabel',background=COLORS['surface'],foreground=COLORS['ink'],font=('Segoe UI',10))
    style.configure('Brand.TLabel',background=COLORS['bg'],foreground=COLORS['ink'],font=('Segoe UI',21,'bold'))
    style.configure('Eyebrow.TLabel',background=COLORS['bg'],foreground=COLORS['muted'],font=('Segoe UI',9))
    style.configure('Section.TLabel',foreground=COLORS['ink'],font=('Segoe UI',15,'bold'))
    style.configure('CardTitle.TLabel',foreground=COLORS['ink'],font=('Segoe UI',12,'bold'))
    style.configure('Muted.TLabel',background=COLORS['surface'],foreground=COLORS['muted'],font=('Segoe UI',9))
    style.configure('PanelCaption.TLabel',background=COLORS['surface'],foreground=COLORS['muted'],font=('Segoe UI',9,'bold'))
    style.configure('Context.TLabel',background=COLORS['surface'],foreground=COLORS['muted'],font=('Segoe UI',9))
    style.configure('TButton',font=('Segoe UI',10),padding=(12,8),background='#EFF4F9',foreground=COLORS['ink'])
    style.map('TButton',background=[('active','#E0EAF5'),('disabled','#F3F4F6')])
    style.configure('Accent.TButton',font=('Segoe UI',10,'bold'),padding=(17,9),background=COLORS['accent'],foreground='white')
    style.map('Accent.TButton',background=[('active','#0B478F'),('disabled','#AFC4DE')],foreground=[('disabled','#F6F9FC')])
    style.configure('Success.TButton',font=('Segoe UI',10,'bold'),padding=(17,9),background=COLORS['ok'],foreground='white')
    style.map('Success.TButton',background=[('active','#115634'),('disabled','#A8CCBA')])
    style.configure('Main.TNotebook',background=COLORS['bg'],borderwidth=0,tabmargins=(0,0,0,0))
    style.configure('Main.TNotebook.Tab',padding=(22,12),font=('Segoe UI',10,'bold'))
    style.map('Main.TNotebook.Tab',background=[('selected',COLORS['surface']),('!selected',COLORS['bg'])],foreground=[('selected',COLORS['accent']),('!selected',COLORS['muted'])])
    style.configure('Treeview',rowheight=31,font=('Segoe UI',10),background=COLORS['surface'],foreground=COLORS['ink'],fieldbackground=COLORS['surface'])
    style.configure('Treeview.Heading',font=('Segoe UI',9,'bold'),background='#EAF0F6',foreground='#42536B',padding=(8,7))
    style.configure('TEntry',padding=(7,6))
    style.configure('TCombobox',padding=(7,6))
    return COLORS
