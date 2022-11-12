#!/usr/local/bin/python3

import os
import time
import shlex
import numpy as np
import random as rd
import subprocess as sp
from scipy import stats
from scipy.stats import norm
from scipy.optimize import minimize
import sklearn.gaussian_process as gp
from test_server import *
from control_vm import *

# Number of LC apps available
TOT_LC_APPS   = 5

# Number of BG apps available
TOT_BG_APPS   = 6

# Number of QPS categories
N_QPS_CAT     = 10

# LC apps
APP_NAMES     = [
                'img-dnn'  ,
                'masstree' ,
                'memcached',
                'specjbb'  ,
                'xapian'
                ]

ranges = [[250, 5000, 250, 10000, 5000], [1000, 15000, 1000, 3000, 14000], [0, 0, 0, 0, 0], [1000, 19000, 1000, 25000, 25000], [100, 1500, 100, 3000, 1000]]
#max_qps = [1250, 5000 * 0.5, 0, 19000, 400 * 2]
#max_qps = [1500, 5000, 0, 16000, 500] #only one guest
#standards = [8.464, 1.921, 0, 0.537, 17.864] #only one guest
max_qps = [1000, 6000, 0, 16000, 600] #three guests
standards = [2570.76, 1331.651, 0, 0.537, 2586.127] #thress guests

# QoS requirements of LC apps (time in seconds)
#APP_QOSES     = {
#                'img-dnn'  : 3.0  ,
#                'masstree' : 2.0  ,
#                'memcached': 225.0,
#                'specjbb'  : 0.5  ,
#                'xapian'   : 12.0 
#                }
APP_QOSES     = {
                'img-dnn'  : 4000.0  ,
                'masstree' : 2000.0  ,
                'memcached': 225.0,
                'specjbb'  : 1000.0  ,
                'xapian'   : 1000.0 
                }
#APP_QOSES     = {
#                'img-dnn'  : 3.0  ,
#                'masstree' : 500.0  ,
#                'memcached': 225.0,
#                'specjbb'  : 0.5  ,
#                'xapian'   : 12.0 
#                }
# QPS levels
APP_QPSES     = {
                'img-dnn'  : list(range(300, 3300, 300))      ,
                'masstree' : list(range(100, 1100, 100))      ,
                'memcached': list(range(20000, 220000, 20000)),
                'specjbb'  : list(range(800, 9600, 800))      ,
                'xapian'   : list(range(800, 9600, 800))
                }

# BG apps
BCKGRND_APPS  = [
                'blackscholes' ,
                'canneal'      ,
                'fluidanimate' ,
                'freqmine'     ,
                'streamcluster',
                'swaptions'
                ]

# Number of times acquisition function optimization is restarted
NUM_RESTARTS  = 1

# Number of maximum iterations (max configurations sampled)
MAX_ITERS     = 100

# Shared Resources hardware configuration:
# Number of Cores (10 units)
# Number of Ways (11 units)
# Percent Memory Bandwidth (10 units)

# Number of resources controlled
NUM_RESOURCES = 3

# Max values of each resources
NUM_CORES     = 10
NUM_WAYS      = 11
MEMORY_BW     = 100

# Max units of (cores, LLC ways, memory bandwidth)
NUM_UNITS     = [10, 11, 10]

# Configuration formats
CONFIGS_CORES = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10"]
CONFIGS_CWAYS = ["0x1", "0x3", "0x7", "0xf", "0x1f", "0x3f", "0x7f", "0xff", "0x1ff", "0x3ff", "0x7ff"]
CONFIGS_MEMBW = ["10", "20", "30", "40", "50", "60", "70", "80", "90", "100"]

# Commands to set hardware allocations
TASKSET       = "taskset -acp "
COS_CAT_SET1  = "pqos-msr -e \"llc:%s=%s\""
COS_CAT_SET2  = "pqos-msr -a \"llc:%s=%s\""
COS_MBG_SET1  = "pqos-msr -e \"mba:%s=%s\""
COS_MBG_SET2  = "pqos-msr -a \"core:%s=%s\""
COS_RESET     = "pqos-msr -R"

# Commands to get MSRs
WR_MSR_COMM       = "wrmsr -a "
RD_MSR_COMM       = "rdmsr -a -u "

# MSR register requirements
IA32_PERF_GBL_CTR = "0x38F"  # Need bits 34-32 to be 1
IA32_PERF_FX_CTRL = "0x38D"  # Need bits to be 0xFFF
MSR_PERF_FIX_CTR0 = "0x309"

# Amount of time to sleep after each sample
SLEEP_TIME    = 5

# Suppress application outputs
FNULL         = open(os.devnull, 'w')

# Path to the base directory (if required)
BASE_DIR      = os.getcwd()

# All the LC apps being run
#LC_APPS       = ['img-dnn', 'masstree', 'xapian']
#perc_qps      = [0.2, 0.2, 0.2]
LC_APPS       = ['img-dnn', 'masstree']
perc_qps      = [1.0, 1.0]

# Path to the latency files of applications
LATS_FILES = [BASE_DIR + '/%s/lats.bin' % lc_app for lc_app in LC_APPS]

# ALl the BG jobs being runs
#BG_APPS       = ['blackscholes']
BG_APPS       = ['parsec.blackscholes']

APPS = LC_APPS + BG_APPS

# PIDs of all the applications in order of APPS
APP_PIDS      = [0] * len(APPS)

# QoSes of LC apps
APP_QOSES     = [APP_QOSES[a] for a in LC_APPS]

# Number of apps currently running
NUM_LC_APPS   = len(LC_APPS)

NUM_BG_APPS   = len(BG_APPS)

NUM_APPS      = NUM_LC_APPS + NUM_BG_APPS

# Total number of parameters
NUM_PARAMS    = NUM_RESOURCES*(NUM_APPS-1)

# Set expected value threshold for termination
EI_THRESHOLD  = 0.01**NUM_APPS

# Global variable to hold baseline performances
BASE_PERFS    = [0.0]*NUM_APPS

# Required global variables
BOUNDS        = None

CONSTS        = None

MODEL         = None

OPTIMAL_PERF  = None

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

class Lat(object):

    def __init__(self, fileName):
        f = open(fileName, 'rb')
        a = np.fromfile(f, dtype=np.uint64)
        self.reqTimes = a.reshape((int(a.shape[0]/3.0), 3))
        f.close()

    def parseQueueTimes(self):
        return self.reqTimes[:, 0]
    
    def parseSvcTimes(self):
        return self.reqTimes[:, 1]
    
    def parseSojournTimes(self):
        return self.reqTimes[:, 2]

vmm = None
first_flag = True

def runLCBenchPre(platform, ind, k):
    print('ind = %d, k = %d, max_qps[ind] = %f, perc_qps[k] = %f' % (ind, k, max_qps[ind], perc_qps[k]))
    if platform == 'host':
        os.system('pkill -9 test_server')
        os.system('pkill -9 %s' % (APP_NAMES[ind]))
        p1 = run_tailbench_parallel_pre(10 + ind, APP_NAMES[ind], max_qps[ind] * perc_qps[k], ranges[ind][3], ranges[ind][4], 1)
        exec_cmd('ps aux | grep %s' % (APP_NAMES[ind]))
        pid = 0
        for line in split_str(get_res(), '\n'):
            if not 'grep' in line and not 'defunct' in line:
                print(line)
                pid = int(list(split_str(line))[1])
                print('pid = ', pid)
        #os.system('kill -STOP %s' % pid)
        return (p1, pid)
    elif platform == 'guest':
        global vmm
        global first_flag
        if first_flag:
            vmm = VMM()
            num_vms = NUM_APPS
            for vm_id in range(0, num_vms):
                sync_file(vm_id)
                vm_name = 'centos8_test%d' % vm_id
                vmm.new_vm(vm_id, vm_name)
            vmm.connect_client()
            vmm.init_mode('tailbench')
            vmm.init_benchmark()
            first_flag = False
        vmm.init_mode('tailbench')
        vmm.run_benchmark_single(k, once = True, task_name = LC_APPS[k])
        return (None, vmm.vms[k].get_pid())

def runLCBenchPost(platform, ind, k, p1 = None):
    #os.system('kill -CONT %s' % pid)
    p95 = 1e6
    if platform == 'host':
        if p1:
            p1.wait()
        p95 = run_tailbench_parallel_post(10 + ind, APP_NAMES[ind], max_qps[ind] * perc_qps[k], ranges[ind][3], ranges[ind][4], 1)
    elif platform == 'guest':
        vmm.run_benchmark_single(k, skip_header = True)
        p95 = float(vmm.vms[k].data)
    return p95

def runBGBenchPre(platform, ind):
    p1 = None
    pid = -1
    if platform == 'host':
        os.system('pkill -9 test_server')
        os.system('pkill -9 %s' % (BG_APPS[ind].split('.')[1]))
        p1 = run_parsec_parallel_pre(ind, BG_APPS[ind], 'native', 16, 1)
        exec_cmd('ps aux | grep %s' % (BG_APPS[ind].split('.')[1]))
        pid = 0
        for line in split_str(get_res(), '\n'):
            if not 'grep' in line and not 'defunct' in line:
                print(line)
                pid = int(list(split_str(line))[1])
                print('pid = ', pid)
    elif platform == 'guest':
        vmm.init_mode('parsec')
        vmm.run_benchmark_single(ind + NUM_LC_APPS, once = True, task_name = BG_APPS[ind])
        p1 = None
        pid = vmm.vms[ind + NUM_LC_APPS].get_pid()
    return (p1, pid)

def runBGBenchPost(platform, ind, p1 = None):
    time = 0
    if platform == 'host':
        if p1:
            p1.wait()
        time = run_parsec_parallel_post(ind, BG_APPS[ind], 'native', 16, 1)
    elif platform == 'guest':
        vmm.run_benchmark_single(ind + NUM_LC_APPS, skip_header = True)
        p95 = float(vmm.vms[ind + NUM_LC_APPS].data)
    print('Running Time: %f' % time)

def getLatPct(latsFile):
    assert os.path.exists(latsFile)
    latsObj = Lat(latsFile)
    sjrnTimes = [l/1e6 for l in latsObj.parseSojournTimes()]
    mnLt = np.mean(sjrnTimes)
    p95  = stats.scoreatpercentile(sjrnTimes, 95.0)
    return p95

def gen_bounds_and_constraints():
    global BOUNDS, CONSTS
    # Generate the bounds and constraints required for the optimizer
    BOUNDS = np.array([[[1, NUM_UNITS[r]-(NUM_APPS-1)] for a in range(NUM_APPS-1)] \
             for r in range(NUM_RESOURCES)]).reshape(NUM_PARAMS, 2).tolist()
    print("BOUNDS = ", BOUNDS)

    CONSTS = []
    for r in range(NUM_RESOURCES):
        CONSTS.append({'type':'eq', 'fun':lambda x: sum(x[r*(NUM_APPS-1):(r+1)*(NUM_APPS-1)]) - (NUM_APPS-1)})
        CONSTS.append({'type':'eq', 'fun':lambda x: -sum(x[r*(NUM_APPS-1):(r+1)*(NUM_APPS-1)]) + (NUM_UNITS[r]-1)})
    print("CONSTS = ", CONSTS)

def gen_initial_configs():

    # Generate the maximum allocation configurations for all applications
    configs = [[1]*NUM_PARAMS for j in range(NUM_APPS)]
    for j in range(NUM_APPS-1):
        for r in range(NUM_RESOURCES):
            configs[j][j+((NUM_APPS-1)*r)] = NUM_UNITS[r] - (NUM_APPS-1)

    # Generate the equal partition configuration
    equal_partition = []
    for r in range(NUM_RESOURCES):
        for j in range(NUM_APPS-1):
            equal_partition.append(int(NUM_UNITS[r]/NUM_APPS))

    configs.append(equal_partition)

    return configs

platform = 'guest'
def get_baseline_perfs(configs):

    global BASE_PERFS
    global platform

    for i in range(NUM_APPS):

        p = configs[i]
    
        # Core allocations of each job
        app_cores = [""]*NUM_APPS
        s = 0
        for j in range(NUM_APPS-1):
            app_cores[j] = ",".join([str(c) for c in list(range(s,s+p[j]))+list(range(s+NUM_UNITS[0],s+p[j]+NUM_UNITS[0]))])
            s += p[j]
        app_cores[NUM_APPS-1] = ",".join([str(c) for c in list(range(s,NUM_UNITS[0]))+list(range(s+NUM_UNITS[0],NUM_UNITS[0]+NUM_UNITS[0]))])
        
        # L3 cache ways allocation of each job
        app_cways = [""]*NUM_APPS
        s = 0
        for j in range(NUM_APPS-1):
            app_cways[j] = str(hex(int("".join([str(1) for w in list(range(p[j+NUM_APPS-1]))]+[str(0) for w in list(range(s))]),2)))
            s += p[j+NUM_APPS-1]
        app_cways[NUM_APPS-1] = str(hex(int("".join([str(1) for w in list(range(NUM_UNITS[1]-s))]+[str(0) for w in list(range(s))]),2)))
        
        # Memory bandwidth allocation of each job
        app_membw = [""]*NUM_APPS
        s = 0
        for j in range(NUM_APPS-1):
            app_membw[j] = str(p[j+2*(NUM_APPS-1)]*10)
            s += p[j+2*(NUM_APPS-1)]*10
        app_membw[NUM_APPS-1] = str(NUM_UNITS[2]*10-s)
        
        print('app_cores = ', app_cores)
        print('app_cways = ', app_cways)
        print('app_membw = ', app_membw)

        #cbw running apps pre
        procs = []
        for k in range(NUM_APPS):
            ind = APP_NAMES.index(LC_APPS[k])
            (p1, pid) = runLCBenchPre(platform, ind, k)
            procs.append(p1)
            APP_PIDS[k] = '%d' % (pid)
        print('new pids = ', APP_PIDS)

        # Set the allocations #cbw
        for j in range(NUM_APPS):
            taskset_cmnd = TASKSET + app_cores[j] + " " + APP_PIDS[j]
            cos_cat_set1 = COS_CAT_SET1 % (str(j+1), app_cways[j])
            cos_cat_set2 = COS_CAT_SET2 % (str(j+1), app_cores[j])
            cos_mBG_set1 = COS_MBG_SET1 % (str(j+1), app_membw[j])
            cos_mBG_set2 = COS_MBG_SET2 % (str(j+1), app_cores[j])
            #sp.check_output(shlex.split(taskset_cmnd), stderr=FNULL)
            #sp.check_output(shlex.split(cos_cat_set1), stderr=FNULL)
            #sp.check_output(shlex.split(cos_cat_set2), stderr=FNULL)
            #sp.check_output(shlex.split(cos_mBG_set1), stderr=FNULL)
            #sp.check_output(shlex.split(cos_mBG_set2), stderr=FNULL)
            exec_cmd(taskset_cmnd)
            exec_cmd(cos_cat_set1)
            exec_cmd(cos_cat_set2)
            exec_cmd(cos_mBG_set1)
            exec_cmd(cos_mBG_set2)

        if i >= NUM_LC_APPS:
            # Reset the IPS counters
            os.system(WR_MSR_COMM + MSR_PERF_FIX_CTR0 + " 0x0")
    
        time.sleep(SLEEP_TIME)

        #cbw running apps post
        for k in range(NUM_APPS):
            ind = APP_NAMES.index(LC_APPS[k])
            perf = runLCBenchPost(platform, ind, k, procs[k])
            #perf = getLatPct(LATS_FILES[k])
            if k == i:
                BASE_PERFS[k] = perf
            print('BASE_PERFS[%d] = %f' % (k, BASE_PERFS[k]))
    
        if i < NUM_LC_APPS:
            pass

            #BASE_PERFS[i] = getLatPct(LATS_FILES[i])
            #print('BASE_PERFS[%d] = %f' % (i, BASE_PERFS[i]))
        else:
            # Get the IPS counters  
            ipsP = os.popen(RD_MSR_COMM + MSR_PERF_FIX_CTR0)
        
            # Calculate the IPS
            IPS = 0.0
            cor = [int(c) for c in app_cores[i].split(',')]
            ind = 0
            for line in ipsP.readlines():
                if ind in cor:
                    IPS += float(line)
                ind += 1
            
            BASE_PERFS[i] = IPS

def gen_random_config():

    # Generate a random configuration
    config = []
    for r in range(NUM_RESOURCES):
        total = 0
        remain_apps = NUM_APPS
        for j in range(NUM_APPS-1):
            alloc = rd.randint(1, NUM_UNITS[r] - (total+remain_apps-1))
            config.append(alloc)
            total += alloc
            remain_apps -= 1

    return config

def sample_perf(p, r_ind = -1):
    global platform

    # Core allocations of each job
    app_cores = [""]*NUM_APPS
    s = 0
    for j in range(NUM_APPS-1):
        app_cores[j] = ",".join([str(c) for c in list(range(s,s+p[j]))+list(range(s+NUM_UNITS[0],s+p[j]+NUM_UNITS[0]))])
        s += p[j]
    app_cores[NUM_APPS-1] = ",".join([str(c) for c in list(range(s,NUM_UNITS[0]))+list(range(s+NUM_UNITS[0],NUM_UNITS[0]+NUM_UNITS[0]))])
    
    # L3 cache ways allocation of each job
    app_cways = [""]*NUM_APPS
    s = 0
    for j in range(NUM_APPS-1):
        app_cways[j] = str(hex(int("".join([str(1) for w in list(range(p[j+NUM_APPS-1]))]+[str(0) for w in list(range(s))]),2)))
        s += p[j+NUM_APPS-1]
    app_cways[NUM_APPS-1] = str(hex(int("".join([str(1) for w in list(range(NUM_UNITS[1]-s))]+[str(0) for w in list(range(s))]),2)))
    
    # Memory bandwidth allocation of each job
    app_membw = [""]*NUM_APPS
    s = 0
    for j in range(NUM_APPS-1):
        app_membw[j] = str(p[j+2*(NUM_APPS-1)]*10)
        s += p[j+2*(NUM_APPS-1)]*10
    app_membw[NUM_APPS-1] = str(NUM_UNITS[2]*10-s)

    print('app_cores = ', app_cores)
    print('app_cways = ', app_cways)
    print('app_membw = ', app_membw)

    #cbw running apps pre
    lc_procs = []
    bg_procs = []
    for k in range(NUM_APPS):
        if k < NUM_LC_APPS:
            ind = APP_NAMES.index(LC_APPS[k])
            (p1, pid) = runLCBenchPre(platform, ind, k)
            lc_procs.append(p1)
        else:
            ind = k - NUM_LC_APPS
            (p1, pid) = runBGBenchPre(platform, ind)
            bg_procs.append(p1)
        APP_PIDS[k] = '%d' % (pid)
    print('new pids = ', APP_PIDS)
    
    # Set the allocations
    for j in range(NUM_APPS):
        taskset_cmnd = TASKSET + app_cores[j] + " " + APP_PIDS[j]
        cos_cat_set1 = COS_CAT_SET1 % (str(j+1), app_cways[j])
        cos_cat_set2 = COS_CAT_SET2 % (str(j+1), app_cores[j])
        cos_mBG_set1 = COS_MBG_SET1 % (str(j+1), app_membw[j])
        cos_mBG_set2 = COS_MBG_SET2 % (str(j+1), app_cores[j])
        #sp.check_output(shlex.split(taskset_cmnd), stderr=FNULL)
        #sp.check_output(shlex.split(cos_cat_set1), stderr=FNULL)
        #sp.check_output(shlex.split(cos_cat_set2), stderr=FNULL)
        #sp.check_output(shlex.split(cos_mBG_set1), stderr=FNULL)
        #sp.check_output(shlex.split(cos_mBG_set2), stderr=FNULL)
        exec_cmd(taskset_cmnd)
        exec_cmd(cos_cat_set1)
        exec_cmd(cos_cat_set2)
        exec_cmd(cos_mBG_set1)
        exec_cmd(cos_mBG_set2)

    if NUM_BG_APPS != 0:
        # Reset the IPS counters
        os.system(WR_MSR_COMM + MSR_PERF_FIX_CTR0 + " 0x0")

    # Wait for some cycles
    time.sleep(SLEEP_TIME)

    sd_bg = [0.0]*NUM_BG_APPS
    if NUM_BG_APPS != 0:
        # Get the IPS counters  
        ipsP = os.popen(RD_MSR_COMM + MSR_PERF_FIX_CTR0)

        for j in range(NUM_BG_APPS):
            # Calculate the IPS
            IPS = 0.0
            cor = [int(c) for c in app_cores[j+NUM_LC_APPS].split(',')]
            ind = 0
            for line in ipsP.readlines():
                if ind in cor:
                    IPS += float(line)
                ind += 1
            print('IPS=', IPS)
            if j + NUM_LC_APPS == r_ind:
                BASE_PERFS[j + NUM_LC_APPS] = IPS
            if r_ind != -1 and r_ind < NUM_LC_APPS:
                BASE_PERFS[j + NUM_LC_APPS] = 1.0 #for error fix
                
            sd_bg[j] = min(1.0, IPS / BASE_PERFS[j+NUM_LC_APPS])
        print('sd_bg=', sd_bg)

    qv = [1.0]*NUM_LC_APPS
    sd = [1.0]*NUM_LC_APPS

    #cbw running apps post
    for j in range(NUM_LC_APPS):
        ind = APP_NAMES.index(LC_APPS[j])
        p95 = runLCBenchPost(platform, ind, j, lc_procs[j])
        #p95 = getLatPct(LATS_FILES[j])
        #cbw
        if ind < NUM_LC_APPS and j == r_ind:
            BASE_PERFS[ind] = p95

        print('QOS[%d] = %f' % (j, p95))
        if p95 > APP_QOSES[j]:
            qv[j] = APP_QOSES[j] / p95
            sd[j] = BASE_PERFS[j] / p95
   
    #cbw
    for j in range(NUM_BG_APPS):
        time_bg = runBGBenchPost(platform, j)

    # Return the final objective function score if QoS not met
    if stats.mstats.gmean(qv) != 1.0:
        print('cbw not met: qv:', qv)
        print('cbw not met: gmean:', 0.5*stats.mstats.gmean(qv))
        return qv, 0.5*stats.mstats.gmean(qv)

    # Return the final objective function score if QoS met
    if NUM_BG_APPS == 0:
        return qv, 0.5*(min(1.0, stats.mstats.gmean(sd))+1.0)

    # Get the IPS counters  
    #ipsP = os.popen(RD_MSR_COMM + MSR_PERF_FIX_CTR0)

    #sd_bg = [0.0]*NUM_BG_APPS
    #for j in range(NUM_BG_APPS):
    #    # Calculate the IPS
    #    IPS = 0.0
    #    cor = [int(c) for c in app_cores[j+NUM_LC_APPS].split(',')]
    #    ind = 0
    #    for line in ipsP.readlines():
    #        if ind in cor:
    #            IPS += float(line)
    #        ind += 1
    #    if j == r_ind:
    #        BASE_PERF[j+NUM_LC_APPS] = IPS
    #        
    #    sd_bg[j] = min(1.0, IPS / BASE_PERFS[j+NUM_LC_APPS])

    #for j in range(NUM_BG_APPS):
    #    t = runBGBenchPost(platform, j, bg_procs[j])

    # Return the final objective function score if BG jobs are present
    return qv, 0.5*(min(1.0,stats.mstats.gmean(sd_bg))+1.0)

def expected_improvement(c, exp=0.01):

    # Calculate the expected improvement for a given configuration 'c'
    mu, sigma = MODEL.predict(np.array(c).reshape(-1, NUM_PARAMS), return_std=True)
    val = 0.0
    with np.errstate(divide='ignore'):
        Z = (mu - OPTIMAL_PERF - exp) / sigma
        val = (mu - OPTIMAL_PERF - exp) * norm.cdf(Z) + sigma * norm.pdf(Z)
        val[sigma == 0.0] = 0.0

    return -1 * val

def find_next_sample(x, q, y):

    # Generate the configuration which has the highest expected improvement potential
    max_config = None
    max_result = 1

    # Multiple restarts to find the global optimum of the acquisition function
    for n in range(NUM_RESTARTS):

        val = None

        # Perform dropout 1/4 of the times
        if rd.choice([True, True, True, False]):

            x0 = gen_random_config()

            val = minimize(fun=expected_improvement,
                           x0=x0,
                           bounds=BOUNDS,
                           constraints=CONSTS,
                           method='SLSQP')
        else:
            ind = rd.choice(list(range(len(y))))
            app = q[ind].index(max(q[ind]))

            if app == (NUM_APPS-1):

                consts = []
                for r in range(NUM_RESOURCES):
                    units = sum(x[ind][r*(NUM_APPS-1):(r+1)*(NUM_APPS-1)])
                    consts.append({'type':'eq', 'fun':lambda x: sum(x[r*(NUM_APPS-1):(r+1)*(NUM_APPS-1)]) - units})
                    consts.append({'type':'eq', 'fun':lambda x: -sum(x[r*(NUM_APPS-1):(r+1)*(NUM_APPS-1)]) + units})

                val = minimize(fun=expected_improvement,
                               x0=x[ind],
                               bounds=BOUNDS,
                               constraints=consts,
                               method='SLSQP')

            else:

                bounds = [[b[0], b[1]] for b in BOUNDS]

                for r in range(NUM_RESOURCES):
                    bounds[app+r*(NUM_APPS-1)][0] = x[ind][app+r*(NUM_APPS-1)]
                    bounds[app+r*(NUM_APPS-1)][1] = x[ind][app+r*(NUM_APPS-1)]

                val = minimize(fun=expected_improvement,
                               x0=x[ind],
                               bounds=bounds,
                               constraints=CONSTS,
                               method='SLSQP')

        if val.fun < max_result:
            max_config = val.x
            max_result = val.fun
    
    return -max_result, [int(c) for c in max_config]

def bayesian_optimization_engine(x0, alpha=1e-5):

    global MODEL, OPTIMAL_PERF

    x_list = []
    q_list = []
    y_list = []

    # Sample initial configurations
    for (t_ind, params) in enumerate(x0):
        print("=================== %sInitail configurations %03d/%03d%s ===================" % (color.beg1, t_ind, len(x0) - 1, color.end))
        x_list.append(params)
        q, y = sample_perf(params, t_ind)
        print('q, y = ', q, y)
        q_list.append(q)
        y_list.append(y)
        
    xp = np.array(x_list)
    yp = np.array(y_list)
    
    # Create the Gaussian process model as the surrogate model
    kernel = gp.kernels.Matern(length_scale=1.0, nu=1.5)
    MODEL  = gp.GaussianProcessRegressor(kernel=kernel, alpha=alpha, n_restarts_optimizer=10, normalize_y=True)
    
    # Iterate for specified number of iterations as maximum
    for n in range(MAX_ITERS):
        print("=================== %sGaussian Iteration %03d%s ===================" % (color.beg1, n, color.end))

        # Update the surrogate model
        MODEL.fit(xp, yp)
        OPTIMAL_PERF = np.max(yp)

        # Find the next configuration to sample
        ei, next_sample = find_next_sample(x_list, q_list, y_list)

        # If the configuration is already sampled, carefully replace the sample
        mind = 0
        while next_sample in x_list:
            if mind == len(y_list):
                next_sample = gen_random_config()
                continue
            ind = sorted(enumerate(y_list), key = lambda x:x[1])[mind][0]
            if stats.mstats.gmean(q_list[ind]) == 1.0:
                mind += 1
                continue
            boxes = sum([q==1.0 for q in q_list[ind]])
            if boxes == 0:
                mind += 1
                continue
            next_sample = [x for x in x_list[ind]]
            for r in range(NUM_RESOURCES):
                avail = NUM_UNITS[r]
                for a in range(NUM_APPS-1):
                    if q_list[ind][a] == 1.0:
                        flip = rd.choice([True, False])
                        if flip and next_sample[r*(NUM_APPS-1)+a] != 1.0:
                            next_sample[r*(NUM_APPS-1)+a] -= 1
                        avail -= next_sample[r*(NUM_APPS-1)+a]
                if q_list[ind][NUM_APPS-1] == 1.0:
                    flip = rd.choice([True, False])
                    unit = NUM_UNITS[r]-sum(next_sample[r*(NUM_APPS-1):(r+1)*(NUM_APPS-1)])
                    if flip and unit != 1.0:
                        avail -= (unit - 1)
                    else:
                        avail -= unit
                cnf = [int(float(avail)/float(NUM_APPS-boxes)) for b in range(NUM_APPS-boxes)]
                cnf[-1] += avail - sum(cnf)
                i = 0
                for a in range(NUM_APPS-1):
                    if q_list[ind][a] != 1.0:
                        next_sample[r*(NUM_APPS-1)+a] = cnf[i]
                        i += 1
            mind += 1

        # Sample the new configuration
        x_list.append(next_sample)
        q, y = sample_perf(next_sample)
        print('q=', q)
        print('y=', y)
        q_list.append(q)
        y_list.append(y)

        xp = np.array(x_list)
        yp = np.array(y_list)

        # Terminate if the termination requirements are met
        if ei < EI_THRESHOLD or np.max(yp) >= 0.99:
            print('ei=', ei)
            print('EI_THRESHOLD=', EI_THRESHOLD)
            print('np.max(np)=', np.max(yp))
            break

    return n+1, np.max(yp)

def standard_test():
    print("=================== standard test begin ===================")
    (p1, pid) = runLCBenchPre('guest', 0, 0)
    #clean
    taskset_cmnd = TASKSET + "0-9,20-29 " + str(pid)
    exec_cmd(taskset_cmnd)
    exec_cmd("pqos -R")

    p95 = runLCBenchPost('guest', 0, 0, p1)
    standard = 6000
    if p95 < standard:
        print("=================== standard test passed: %f < %f ===================" % (p95, standard))
    else:
        print("=================== standard test failed: %f >= %f ===================" % (p95, standard))
        sys.exit(1)

def c_lite():

    #cbw
    standard_test()
    
    # Generate the bounds and constraints required for optimization
    gen_bounds_and_constraints()

    # Generate the initial set of configurations
    init_configs = gen_initial_configs()
    print('init_configs = ', init_configs)

    # Get the baseline performances with maximum allocations for each application
    #get_baseline_perfs(init_configs)

    # Perform Bayesian optimization
    num_iters, obj_value = bayesian_optimization_engine(x0=init_configs)

    return num_iters, obj_value

def main():

    # Switch on the performance counters
    os.system(WR_MSR_COMM + IA32_PERF_GBL_CTR + " 0x70000000F")
    os.system(WR_MSR_COMM + IA32_PERF_FX_CTRL + " 0xFFF")

    # Print the header
    st0 = ''
    for a in range(NUM_APPS):
        st0 += 'App' + str(a) + ','
    st0 += 'ObjectiveValue' + ','
    st0 += '#Iterations'

    # Execute C-LITE
    num_iters, obj_value = c_lite()

    # Print the final results
    st1 = ''
    for a in LC_APPS:
        st1 += a + ','
    for a in BG_APPS:
        st1 += a + ','
    st1 += '%.2f'%obj_value + ','
    st1 += '%.2f'%num_iters

    print(st0)
    print(st1)

if __name__ == '__main__':

    # Invoke the main function
    main()
