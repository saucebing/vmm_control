#!/usr/local/bin/python3
import os, sys, time, subprocess, tempfile, re
import matplotlib
import matplotlib.pyplot as plt
out_temp = [None] * 1024
fileno = [None] * 1024

def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

def exec_cmd(cmd, index = 0, wait = True, vm_id = 0):
    global out_temp, fileno
    print('[VM%d]: CMD: ' % vm_id, cmd)
    out_temp[index] = tempfile.SpooledTemporaryFile()
    fileno[index] = out_temp[index].fileno()
    p1 = subprocess.Popen(cmd, stdout = fileno[index], stderr = fileno[index], shell=True)
    if wait:
        p1.wait()
    out_temp[index].seek(0)
    return p1

def parallel_cmd(cmd, num, wait = True):
    global out_temp, fileno
    p = []
    for i in range(0, num):
        out_temp[i] = tempfile.SpooledTemporaryFile()
        fileno[i] = out_temp[i].fileno()
        real_cmd = '%s %d' % (cmd, i)
        print('CMD: ', real_cmd)
        p.append(subprocess.Popen(real_cmd, stdout = fileno[i], stderr = fileno[i], shell=True))
    for i in range(0, num):
        if wait:
            p[i].wait()
        out_temp[i].seek(0)
    return p

def find_str(pattern, string):
    pat = re.compile(pattern)
    return pat.findall(string)[0]

def find_list(pattern, lst):
    pat = re.compile(pattern)
    return [item for item in lst if pat.findall(item)]

def find_list_2(pattern, lst):
    pat = re.compile(pattern)
    return [pat.findall(item)[0] for item in lst if pat.findall(item)]

def split_str(string, char=' '):
    return list(filter(lambda x:x, string.split(char)))

def b2s(s):
    return str(s, encoding = 'utf-8')

def get_res(index = 0):
    global out_temp, fileno
    return b2s(out_temp[index].read())

def transform(a, a_min, a_max, b_min, b_max):
    return (a - a_min) / (a_max - a_min) * (b_max - b_min) + b_min

def transform_list(a, a_min, a_max, b_min, b_max):
    return [transform(item, a_min, a_max, b_min, b_max) for item in a]

def cvalue(a):
    c = int(256 * a - 1)
    res = '#%02x%02x%02x' % (c, c, c)
    return res

def cvalue_list(a):
    return [cvalue(item) for item in a]

def sync_file(ind):
    cmd = 'scp -r /root/vmm_control test%s:/root/' % ind
    exec_cmd(cmd)
    print(get_res())

class color:
    black = '\033[0;30m'
    red = '\033[0;31m'
    green = '\033[0;32m'
    yellow = '\033[0;33m'
    blue = '\033[0;34m'
    purple = '\033[0;35m'
    dark_green = '\033[0;36m'
    white = '\033[0;37m'
    grey = '\033[90m'
    l_red = '\033[91m' #fail
    l_green = '\033[92m'
    l_yellow = '\033[93m' #warn
    l_blue = '\033[94m' #blue
    l_purple = '\033[95m'
    l_dark_green = '\033[96m'
    end = '\033[0m'
    bold = '\033[1m'
    underline = '\033[4m'

    b_black = '\033[0;40m'
    b_read = '\033[0;41m'
    b_green = '\033[0;42m'
    b_yellow = '\033[0;43m'
    b_blue = '\033[0;44m'
    b_purple = '\033[0;45m'
    b_dark_green = '\033[0;46m'
    b_white = '\033[0;47m'
    b_grey = '\033[100m'
    b_l_red = '\033[101m' #fail
    b_l_green = '\033[102m'
    b_l_yellow = '\033[103m' #warn
    b_l_blue = '\033[104m' #blue
    b_l_purple = '\033[105m'
    b_l_dark_green = '\033[106m'

    beg1 = green + bold
    beg2 = blue + bold
    beg3 = green + bold
    beg4 = blue + bold
    beg5 = yellow + bold
    beg6 = white
    beg7 = red + bold

class Draw:
    draw_mode = False
    num_figs = 0
    xlabels = []
    ylabels = []
    legends = []
    figdir = 'figdir'

    figs = []
    axs = []

    xticks = []
    xticklabels = []

    titles = None

    bar_width = 0.2

    def __init__(self):
        pass

    def pre_draw(self, draw_mode = False, figdir = 'figdir', num_figs = 1, xlabels = [], ylabels = [], titles = [], xaxis = [], legends = []):
        self.draw_mode = draw_mode
        self.figdir = figdir
        self.num_figs = num_figs
        self.xlabels = xlabels
        self.ylabels = ylabels
        self.legends = legends
        self.titles = titles

        if not os.path.exists(self.figdir):
            os.mkdir(self.figdir)

        if self.draw_mode:
            #for f_id in range(0, num_figs):
            #    fig, ax = plt.subplots()
            #    self.figs.append(fig)
            #    self.axs.append(ax)

            #fig, axs = plt.subplots(3, 3, sharey = True)
            #for f_id in range(0, num_figs):
            #    self.axs.append(axs[int(f_id / 3), f_id % 3])

            fig = plt.figure(figsize = (15, 10))
            self.figs = fig
            for f_id in range(0, num_figs):
                self.axs.append(fig.add_subplot(231 + f_id))

    def bar(self, fig_ind, x, Y, latency):
        if self.draw_mode:
            for (yid, y) in enumerate(Y):
                y_str = ['%.1f' % yitem for yitem in y]
                newx = [xitem - self.bar_width / 2 + yid * self.bar_width for xitem in x]
                self.axs[fig_ind].bar(newx, y, width=self.bar_width, label = self.legends[yid])
                for (xid, xitem) in enumerate(newx):
                    if xid < 3:
                        latency_value = float(latency[yid][xid])
                        latency_str = '%.1f' % latency_value
                        if latency_value > 10:
                            latency_str = '%.0f' % latency_value
                        self.axs[fig_ind].text(xitem, y[xid], latency_str, ha = 'center', va = 'bottom', fontsize=6, color = 'black')
                        self.axs[fig_ind].text(xitem, y[xid] + 10, y_str[xid], ha = 'center', va = 'bottom', fontsize=6, color = 'blue')
                    else:
                        self.axs[fig_ind].text(xitem, y[xid], y_str[xid], ha = 'center', va = 'bottom', fontsize=6, color = 'black')
                    if yid == 1:
                        if xid < 3:
                            self.axs[fig_ind].text(xitem, y[xid] + 20, '%.1f%%' % ((Y[1][xid] / Y[0][xid] - 1) * 100), ha = 'center', va = 'bottom', fontsize=6, color = 'red')
                        else:
                            self.axs[fig_ind].text(xitem, y[xid] + 10, '%.1f%%' % ((Y[1][xid] / Y[0][xid] - 1) * 100), ha = 'center', va = 'bottom', fontsize=6, color = 'red')
                self.xticks = list(range(1, len(y) + 1))
                self.xticklabels = ['ID', 'MS', 'BS', 'ALL']

    def post_draw(self):
        if self.draw_mode:
            for f_id in range(0, self.num_figs):
                #title = '%s-%s(%s)' % (self.ylabels[f_id], self.xlabels[f_id], self.titles[f_id])
                self.axs[f_id].set_title(self.titles[f_id])
                if self.xticks:
                    self.axs[f_id].set_xticks(self.xticks)
                    self.axs[f_id].set_xticklabels(self.xticklabels)
                #self.axs[f_id].set_xlabel(xlabels[f_id])
                self.axs[f_id].set_ylabel(ylabels[f_id])
                self.axs[f_id].set_ylim([0,300])
                #self.axs[f_id].set_yscale('log')
                #self.axs[f_id].grid('on')
                #plt.legend(loc='lower left')
                #self.axs[f_id].legend(loc='best')
                self.axs[f_id].legend(loc='upper left')
                #self.axs[f_id].legend(loc=2, bbox_to_anchor=(1.05,1.0), borderaxespad = 0.) 
                #self.axs[f_id].legend(loc=2, bbox_to_anchor=(1.0, 1.0))
                #size = figs[f_id].get_size_inches()
                #print(size)
                #width = 6.4
                #height = 4.8
                #self.figs[f_id].set_figwidth(width  * 1.3)
            self.figs.tight_layout()
            plt.subplots_adjust(top = 1 - 0.04, bottom = 0.04, wspace = 0.2, hspace = 0.25)
            #file_name = "%s/%s.eps" % (self.figdir, 'results')
            #self.figs.savefig(file_name, bbox_inches='tight')
            plt.show()

fnames = find_list('^00.*5.log$', os.listdir('.'))
print(fnames)
fnames.sort()
num_figs = len(fnames)
xlabels = ['9(%d)' % (i + 1) for i in range(0, num_figs)]
ylabels = ['Score'] * num_figs
legends = ['Uniform Partitioning', 'Our Method']
titles = [''] * num_figs
draw = Draw()
draw.pre_draw(draw_mode = True, num_figs = num_figs, xlabels = xlabels, ylabels = ylabels, legends = legends, titles = titles)

for (f_id, fname) in enumerate(fnames):
    group_scores = []
    group_latencys = []
    print('fname = ', fname)
    percs = find_str('(0\.[0-9]*)_(0\.[0-9]*)', fname)
    draw.titles[f_id] = 'Optimization Results of (%d%%, %d%%) Load' % (int(float(percs[0]) * 100), int(float(percs[1]) * 100))
    print(draw.titles[f_id])
    base_line = find_list('BaseScore', split_str(open(fname, 'r').read(), '\n'))[-1]
    best_line = find_list('BestScore', split_str(open(fname, 'r').read(), '\n'))[-1]
    print('base_line = ', base_line)
    print('best_line = ', best_line)
    base_total_score = float(find_str('BaseScore: ([0-9\.]*)', base_line))
    best_total_score = float(find_str('BestScore: ([0-9\.]*)', best_line))
    print('base_total_score = ', base_total_score)
    print('best_total_score = ', best_total_score)
    print('%.2f%%' % ((best_total_score - base_total_score) / base_total_score * 100))
    base_score_str = find_str('base: \[\'([0-9\.]*)\', \'([0-9\.]*)\', \'([0-9\.]*)\'\]', base_line)
    best_score_str = find_str('best: \[\'([0-9\.]*)\', \'([0-9\.]*)\', \'([0-9\.]*)\'\]', best_line)
    base_score = [float(item) for item in base_score_str]
    best_score = [float(item) for item in best_score_str]
    print('base_score = ', base_score)
    print('best_score = ', best_score)
    base_latency_str = find_str('base: \[\'[0-9\.]*\', \'[0-9\.]*\', \'[0-9\.]*\'\], \[\'([0-9\.]*)\', \'([0-9\.]*)\', \'([0-9\.]*)\'\]', base_line)
    best_latency_str = find_str('best: \[\'[0-9\.]*\', \'[0-9\.]*\', \'[0-9\.]*\'\], \[\'([0-9\.]*)\', \'([0-9\.]*)\', \'([0-9\.]*)\'\]', best_line)
    base_latency = [float(item) for item in base_latency_str]
    best_latency = [float(item) for item in best_latency_str]
    print(base_latency)
    print(best_latency)

    base_score.append(base_total_score)
    best_score.append(best_total_score)
    group_scores.append(base_score)
    group_scores.append(best_score)
    group_latencys.append(base_latency)
    group_latencys.append(best_latency)
    draw.bar(f_id, list(range(1,len(base_score) + 1)), group_scores, group_latencys)

draw.post_draw()
