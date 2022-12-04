#!/usr/local/bin/python3
import os, sys, time, subprocess, re
import server
import signal
from datetime import datetime
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
from test_server import *

Procs = [None] * 1024

def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

def exec_cmd(cmd, index = 0, wait = True):
    global Procs
    print('CMD: ', cmd)
    p1 = subprocess.Popen(cmd, stdout = subprocess.PIPE, stderr = subprocess.PIPE, shell=True, close_fds=True, preexec_fn=os.setsid)
    Procs[index] = p1
    if wait:
        p1.wait()
    return p1

def parallel_cmd(cmd, num, wait = True):
    global Procs
    for i in range(0, num):
        real_cmd = '%s %d' % (cmd, i)
        print('CMD: ', real_cmd)
        p = subprocess.Popen(real_cmd, stdout = subprocess.PIPE, stderr = subprocess.PIPE, shell=True, close_fds=True, preexec_fn=os.setsid)
        Procs[i] = p
    for i in range(0, num):
        if wait:
            Procs[i].wait()
    return Procs[:num]

def find_str(pattern, string):
    pat = re.compile(pattern)
    return pat.findall(string)[0].strip()

def find_str2(pattern, string):
    pat = re.compile(pattern)
    return pat.findall(string)[-1]

def split_str(string, char = ' '):
    return filter(lambda x:x, string.split(char))

def b2s(s):
    return str(s, encoding = 'utf-8')

def get_res(ind = 0):
    global Procs
    return b2s(Procs[ind].stdout.read())

class Draw:
    num_figs = 0
    xlabels = []
    ylabels = []

    figs = []
    axs = []

    axis = []

    def __init__(self):
        pass

    def pre_draw(self, num_figs, xlabels, ylabels, titles, xaxis):
        self.num_figs = num_figs
        for f_id in range(0, num_figs):
            fig, ax = plt.subplots()
            self.figs.append(fig)
            self.axs.append(ax)
        self.xlabels = xlabels
        self.ylabels = ylabels
        self.titles = titles
        self.xaxis = xaxis

    def post_draw(self, num_figs):
        figdir = 'figs'
        if not os.path.exists(figdir):
            os.mkdir(figdir)
        for f_id in range(0, num_figs):
            title = '%s-%s(%s)' % (self.ylabels[f_id], self.xlabels[f_id], self.titles[f_id])
            self.axs[f_id].set_title(title)
            if self.xaxis[f_id]:
                self.axs[f_id].set_xticks(xaxis[f_id])
            self.axs[f_id].set_xlabel(xlabels[f_id])
            self.axs[f_id].set_ylabel(ylabels[f_id])
            self.axs[f_id].set_yscale('log')
            #self.axs[f_id].grid('on')
            #plt.legend(loc='lower left')
            self.axs[f_id].legend(loc='best')
            #self.axs[f_id].legend(loc=2, bbox_to_anchor=(1.05,1.0), borderaxespad = 0.) 
            #self.axs[f_id].legend(loc=2, bbox_to_anchor=(1.0, 1.0))
            #size = figs[f_id].get_size_inches()
            #print(size)
            #width = 6.4
            #height = 4.8
            #self.figs[f_id].set_figwidth(width  * 1.3)
            #self.figs[f_id].tight_layout()
            #file_name = "%s/%s.eps" % (figdir, title)
            #file_name = file_name.replace(' ', '_')
            #self.figs[f_id].savefig(file_name, bbox_inches='tight')

benchs = ['img-dnn', 'masstree', 'moses', 'silo', 'specjbb', 'xapian']

file_index = 0
cmd = 'cat test_guest%d.txt | grep -E "bench = |95th"' % file_index
exec_cmd(cmd)
f = open('res_%d.txt' % file_index, 'w')
f.write(get_res())
f.close()

f = open('res_%d.txt' % file_index, 'r')
lines = f.readlines()
f.close()

two_lines = [lines[ind: ind + 2] for ind in range(0, len(lines), 2)]

draw = Draw()
#fig parameters
num_figs = len(benchs)
xlabels = ['QPS'] * num_figs
ylabels = ['95th percentile latency (ms)'] * num_figs
titles = benchs
legends = benchs
xaxis = [[]] * num_figs
draw_mode = True
if draw_mode:
    draw.pre_draw(num_figs, xlabels, ylabels, titles, xaxis)
offset_x = 1.05
offset_y = 0.9
for (bench_id, bench_name) in enumerate(benchs):
    qps_arr = []
    p95_arr = []
    for two_line in two_lines:
        if bench_name in two_line[0]:
            qps = int(find_str('QPS = ([0-9]+),', two_line[0]))
            p95 = float(find_str('95th percentile latency ([0-9.]+) ms', two_line[1]))
            qps_arr.append(qps)
            p95_arr.append(p95)
    #print(','.join(qps_arr))
    #print(','.join(p95_arr))
    max_ind = 0
    max_ratio = 0
    for i in range(1, len(qps_arr) - 1):
        ratio = (p95_arr[i + 1] - p95_arr[i - 1]) / (qps_arr[i + 1] - qps_arr[i - 1])
        if ratio > max_ratio:
            max_ratio = ratio
            max_ind = i
    if draw_mode:
        draw.axs[bench_id].plot(qps_arr, p95_arr, label = legends[bench_id])
        draw.axs[bench_id].scatter(qps_arr[max_ind], p95_arr[max_ind], color='red')
        draw.axs[bench_id].text(qps_arr[max_ind] * offset_x, p95_arr[max_ind] * offset_y, '(%d, %.2f)' % (qps_arr[max_ind], p95_arr[max_ind]), color='red')
    print('x: ', min(qps_arr), max(qps_arr))
    print('y: ', min(p95_arr), max(p95_arr))
    print('benchs: %s' % (benchs[bench_id]), qps_arr[max_ind], p95_arr[max_ind])
if draw_mode:
    draw.post_draw(num_figs)
    plt.show()
