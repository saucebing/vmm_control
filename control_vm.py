#!/usr/local/bin/python3
import os, sys, time, subprocess, tempfile, re
import client, timeit
from bidict import bidict
from collections import Counter
import pickle
import random
import paramiko

import numpy as np
import matplotlib
#matplotlib.use('TkAgg')
matplotlib.use('pdf')
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from scipy.interpolate import splev, splrep

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
    cmd = 'scp -r /root/vmm_control test%d:/root/' % ind
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

class VM:
    vmm = None
    vm_name = ''
    vm_id = 0
    ip = ''
    state = ''
    client = None
    port = 0

    num_cores = 0
    begin_core = 0
    bench_id = 0
    data = 0 #running time

    llc_ways_beg = 0
    llc_ways_end = 1
    llc_bitlist = []
    memb = 100
    
    llc_range = 1

    def __init__(self, vmm, vm_id, vm_name):
        self.vmm = vmm
        self.vm_id = vm_id
        self.vm_name = vm_name
        self.client = client.CLIENT()
        state = self.get_state()

        self.llc_range = self.vmm.LLC_MAX
        self.llc_ways_beg = 0
        self.llc_ways_end = self.vmm.LLC_MAX
        self.llc_bitlist = [1] * self.vmm.LLC_MAX
        self.memb = 100

        self.llc_range = 1
        #self.print(self.state)

    def print(self, *argc, **kwargs):
        print('[VM%d]:' % self.vm_id, *argc, **kwargs)

    def get_ip(self):
        cmd1 = '{"execute":"guest-network-get-interfaces"}'
        cmd = "virsh qemu-agent-command %s '%s'" % (self.vm_name, cmd1)
        exec_cmd(cmd, vm_id = self.vm_id)
        content = get_res()
        #self.ip = find_str('(192\.168\.122\.[0-9]+)', content)
        self.ip = find_str('(192\.168\.[0-9]+\.[0-9]+)', content)
        self.print(self.ip)

    def get_state(self):     #running, shut off
        cmd = 'virsh dominfo --domain %s' % self.vm_name
        exec_cmd(cmd, vm_id = self.vm_id)
        content = get_res()
        self.state = find_str('State: (.*)', content).strip()
        self.num_cores = int(find_str('CPU\(s\): (.*)', content).strip())

    def set_port(self, port):
        self.port = port
        self.client.set_port(self.port)

    def connect(self):
        self.get_state()
        if self.state == 'running':
            self.get_ip()
        self.print('ip:', self.ip)
        self.client.set_ip(self.ip)
        self.client.connect()

    def send(self, msg):
        self.client.send(msg)

    def client_close(self):
        self.client.client_close()

    def recv(self):
        return self.client.recv()

    def shutdown(self):
        vm.get_state()
        if self.state == 'running':
            cmd = 'virsh shutdown %s' % self.vm_name
            exec_cmd(cmd, vm_id = self.vm_id)

    def start(self):
        vm.get_state()
        if self.state == 'shut off':
            cmd = 'virsh start %s' % self.vm_name
            exec_cmd(cmd, vm_id = self.vm_id)

    def suspend(self):
        cmd = 'virsh suspend %s' % self.vm_name
        exec_cmd(cmd, vm_id = self.vm_id)

    def resume(self):
        cmd = 'virsh resume %s' % self.vm_name
        exec_cmd(cmd, vm_id = self.vm_id)

    def get_pid(self):
        cmd = 'ps aux | grep kvm'
        exec_cmd(cmd, vm_id = self.vm_id)
        lines = get_res().split('\n')
        pid = 0
        for line in lines:
            if self.vm_name in line:
                pid = int(split_str(line)[1])
                break
        return pid

    def get_spid(self):
        pid = self.get_pid()
        spids = []
        for i in range(0, self.num_cores):
            spids.append([])
        cmd = 'ps -T -p %d' % pid
        exec_cmd(cmd, vm_id = self.vm_id)
        lines = get_res().split('\n')
        for line in lines:
            if 'CPU' in line and 'KVM' in line:
                line2 = split_str(line)
                vcpu_id = int(find_str('([0-9]+)/KVM', line2[5]))
                spids[vcpu_id] = int(line2[1])
        return spids

    def bind_core(self, vcpu, pcpu): #pcpu可以是0-143
        cmd = 'virsh vcpupin %s %s %s' % (self.vm_name, vcpu, pcpu)
        exec_cmd(cmd, vm_id = self.vm_id)

    def bind_mem(self): #pcpu可以是0-143
        pid = self.get_pid()
        cmd = 'migratepages %d all 0' % pid
        exec_cmd(cmd, vm_id = self.vm_id)

    def setvcpus_sta(self, n_vcpu): #set up when shutting down
        cmd = 'virsh setvcpus %s --maximum %d --config' % (self.vm_name, n_vcpu)
        exec_cmd(cmd, vm_id = self.vm_id)

    def setvcpus_dyn(self, n_vcpu):
        cmd = 'virsh setvcpus %s %d' % (self.vm_name, n_vcpu)
        exec_cmd(cmd, vm_id = self.vm_id)

    def setmem_sta(self, mem):
        cmd = 'virsh setmaxmem %s %dG --config' % (self.vm_name, mem)
        exec_cmd(cmd, vm_id = self.vm_id)

    def setmem_dyn(self, mem):
        cmd = 'virsh setmem %s %dG' % (self.vm_name, mem)
        exec_cmd(cmd, vm_id = self.vm_id)

class VMM:
    LLC_MAX = 11
    maps_vm_core = bidict()
    visited = []
    vms = []
    num_vms = 0
    record = []
    records = []
    p = ''
    #benchs = ['splash2x.water_nsquared', 'splash2x.water_spatial', 'splash2x.raytrace', 'splash2x.ocean_cp', 'NPB.CG', 'NPB.FT', 'NPB.SP', 'splash2x.ocean_ncp', 'splash2x.fmm', 'parsec.swaptions', 'NPB.EP', 'parsec.canneal', 'parsec.freqmine']
    #benchs = ['splash2x.water_nsquared', 'splash2x.water_spatial', 'splash2x.raytrace', 'splash2x.ocean_cp', 'splash2x.ocean_ncp', 'splash2x.fmm', 'parsec.swaptions', 'parsec.canneal', 'parsec.freqmine']
    #benchs = ['mysql']
    #benchs = ['memcached']
    benchs = ['img-dnn', 'masstree', 'moses', 'silo', 'specjbb', 'xapian']
    #begin_qps, end_qps, interval_qps, reqs, warmupreqs
    ranges = [[250, 5000, 250, 10000, 5000], [1000, 15000, 1000, 3000, 14000], [5, 100, 5, 500, 500], [1000, 15000, 1000, 20000, 20000], [1000, 19000, 1000, 25000, 25000], [100, 1500, 100, 3000, 1000]]

    #for clite and myalg
    max_qps = [1500, 6000, 0, 17000, 600] #three guests
    standards = [1917.28, 719.39, 0, 130.55, 2061.68] #thress guests
    #perc_qps = [1.0, 1.0, 1.0, 1.0, 1.0]
    perc_qps = [0.5, 0.5, 0.5, 0.5, 0.5]
    #benchs = ['splash2x.water_nsquared', 'splash2x.water_spatial', 'splash2x.raytrace', 'splash2x.ocean_cp', 'splash2x.ocean_ncp', 'splash2x.fmm', 'parsec.swaptions']
    #benchs = ['splash2x.water_nsquared', 'splash2x.water_spatial', 'splash2x.raytrace', 'splash2x.ocean_cp', 'splash2x.ocean_ncp', 'splash2x.fmm', 'parsec.swaptions']
    #benchs = ['parsec.canneal', 'parsec.freqmine']
    #benchs = ['NPB.CG', 'NPB.FT', 'NPB.SP', 'NPB.EP']
    #benchs = ['splash2x.water_nsquared', 'splash2x.water_spatial', 'splash2x.raytrace', 'splash2x.ocean_cp', 'NPB.CG', 'NPB.FT', 'NPB.SP', 'splash2x.ocean_ncp', 'splash2x.fmm', 'parsec.swaptions', 'NPB.EP']
    #benchs = ['splash2x.raytrace']
    #benchs = ['splash2x.raytrace', 'splash2x.ocean_ncp', 'splash2x.barnes', 'splash2x.lu_cb', 'splash2x.radiosity', 'splash2x.water_spatial', 'parsec.fluidanimate', 'parsec.freqmine', 'parsec.ferret', 'parsec.blackscholes']
    #benchs = ['splash2x.raytrace', 'splash2x.ocean_ncp', 'splash2x.water_spatial']

    #benchs = ['splash2x.raytrace', 'splash2x.ocean_ncp', 'splash2x.water_spatial', 'parsec.blackscholes']
    #benchs = ['splash2x.raytrace', 'splash2x.ocean_ncp', 'splash2x.water_spatial', 'parsec.blackscholes']

    bench_id = 0
    run_index = 0
    N_CORE = 0 #number of logical cores
    H_CORE = 0 #number of logical cores in one socket
    Q_CORE = 0 #number of logical cores in one socket
    N_RDT = 0 #number of RDT metrics
    N_FREQ = 0 #number of frequency metrics
    params = []
    mode = ''
    metric_set_mode = False
    metric_get_mode = False

    def __init__(self):
        cmd = 'cat /proc/cpuinfo | grep processor | wc -l'
        exec_cmd(cmd)
        n_core = int(get_res().strip())
        VMM.N_CORE = int(n_core)
        VMM.H_CORE = int(VMM.N_CORE / 2)
        VMM.Q_CORE = int(VMM.N_CORE / 4)
        VMM.N_RDT = 5
        VMM.N_FREQ = 2
        VMM.visited = [False] * VMM.N_CORE

        data_dir = 'records'
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)

    def new_vm(self, vm_id, vm_name):
        vm = VM(self, vm_id, vm_name)
        self.vms.append(vm)
        self.num_vms = len(self.vms)
        self.params.append([])

    def set_mem(self, vm_id, mem):
        vm = self.vms[vm_id]
        vm.setmem_dyn(mem)

    def set_cores(self, vm_id, num_cores, begin_core = 0, same_core = 0):
        num_pcores = int(num_cores / 2)
        local_core_id = 0
        for global_core_id in (list(range(begin_core, VMM.Q_CORE)) + list(range(0, begin_core))):
            if not VMM.visited[global_core_id]:
                if begin_core == 0 and vm_id != 0:
                    global_core_id -= int(same_core / 2)
                self.maps_vm_core[(vm_id, local_core_id)] = global_core_id
                local_core_id += 1
                VMM.visited[global_core_id] = True
                self.maps_vm_core[(vm_id, local_core_id)] = global_core_id + VMM.H_CORE
                local_core_id += 1
                VMM.visited[global_core_id + VMM.H_CORE] = True
                if local_core_id == num_cores:
                    break
        print('maps_vm_core:', self.maps_vm_core)
        vm = self.vms[vm_id]
        vm.setvcpus_dyn(num_cores)
        vm.num_cores = num_cores
        for i in range(0, num_cores):
            vm.bind_core(i, self.maps_vm_core[(vm.vm_id, i)])
        vm.bind_mem()

    def get_rdt(self):
        exec_cmd('pqos -i 30 -t 3')
        res = get_res()
        #print(res)
        res = res.split('\n')
        ind = 0
        while not 'CORE' in res[ind]:
            ind += 1
        ind += 1
        while not 'CORE' in res[ind]:
            ind += 1
        rdts = []
        for i in range(0, VMM.N_RDT):
            rdts.append({})
        for (ind, line) in enumerate(res[ind + 1: ind + VMM.Q_CORE + 1] + res[ind + VMM.H_CORE + 1: ind + VMM.H_CORE + VMM.Q_CORE + 1]):
            aline = line.split()
            rdts[0][int(aline[0])] = float(aline[1]) #ipc
            rdts[1][int(aline[0])] = float(aline[2][:-1]) #miss
            rdts[2][int(aline[0])] = float(aline[3]) #LLC (KB)
            rdts[3][int(aline[0])] = float(aline[4]) #MBL (MB/s)
            rdts[4][int(aline[0])] = float(aline[5]) #MBR (MB/s)
        return rdts

    def get_freq(self):
        exec_cmd('turbostat -q -i 0.5 -n 1')
        res = get_res()
        #print(res)
        res = res.split('\n')
        ind = 0
        while not 'Package' in res[ind]:
            ind += 1
        freqs = []
        for i in range(0, VMM.N_FREQ):
            freqs.append({})
        for (ind, line) in enumerate(res[ind + 2: ind + 2 + VMM.N_CORE]):
            aline = line.split()
            freqs[0][int(aline[2])] = float(aline[3]) #avg_freq
            freqs[1][int(aline[2])] = float(aline[5]) #bzy_freq
        return freqs

    def get_avg(self, mets, num):
        met_sum = {}
        for i in range(0, VMM.Q_CORE):
            met_sum[i] = 0
            met_sum[i + VMM.H_CORE] = 0
        for met in mets:
            for i in range(0, VMM.Q_CORE):
                met_sum[i] += met[i];
                met_sum[i + VMM.H_CORE] += met[i + VMM.H_CORE];
        for i in range(0, int(self.N_CORE / 4)):
            met_sum[i] /= num
            met_sum[i + VMM.H_CORE] /= num
        return met_sum

    def get_metrics(self, num):
        mets = []
        avg_mets = []
        N_METRICS = VMM.N_FREQ + VMM.N_RDT
        for i in range(0, N_METRICS):
            mets.append([])
        for i in range(0, num):
            rdt = self.get_rdt()
            freq = self.get_freq()
            mets[0].append(freq[0])
            mets[1].append(freq[1])
            mets[2].append(rdt[0])
            mets[3].append(rdt[1])
            mets[4].append(rdt[2])
            mets[5].append(rdt[3])
            mets[6].append(rdt[4])
        for met in mets:
            avg_mets.append(self.get_avg(met, num))
        return avg_mets

    def vm_met(self, vm_id, met):
        vm = self.vms[vm_id]
        num_cores = vm.num_cores
        met_total = 0
        for id_core in range(0, num_cores):
            met_total += met[self.maps_vm_core[(vm_id, id_core)]]
        met_avg = met_total / num_cores
        return met_avg

    def vm_metrics(self, vm_id, num_sample, res):
        #self.vms[vm_id].print('freq_rea, frea_bsy and ipc:', res)
        met_vm = []
        for r in res:
            met_vm.append(self.vm_met(vm_id, r))
        self.vms[vm_id].print('freq_rea_vm, freq_bsy_vm and ipc_vm is: ', met_vm[0], met_vm[1], met_vm[2])
        return met_vm

    def end_stage1(self, num_cores, begin_core):
        if self.mode == 'num_cores':
            return (self.num_vms == 1 and num_cores == VMM.H_CORE) or (self.num_vms == 2 and num_cores == VMM.H_CORE - 4)
        elif self.mode == 'tailbench':
            return True
        elif self.mode == 'parsec':
            return True
        elif self.mode == 'begin_core':
            return begin_core == num_cores
        elif self.mode == 'llc':
            return self.vms[0].llc_ways_end == VMM.LLC_MAX
        elif self.mode == 'memb':
            return self.vms[0].memb == 100
        elif self.mode == 'share_llc':
            return self.vms[0].llc_ways_end == self.vms[0].llc_range
        elif self.mode == 'super_share':
            return True

    def end_stage2(self):
        if self.mode == 'num_cores' or self.mode == 'begin_core' or self.mode == 'llc' or self.mode == 'memb':
            return self.run_index == len(self.benchs) - 1
        elif self.mode == 'tailbench':
            return self.run_index == len(self.benchs) - 1
        elif self.mode == 'parsec':
            return self.run_index == len(self.benchs) - 1
        elif self.mode == 'share_llc':
            return self.vms[0].llc_range == VMM.LLC_MAX
        elif self.mode == 'super_share':
            return self.run_index == 5

    def init_mode(self, mode):
        self.mode = mode #num_cores, begin_core

    def clear_records(self):
        #new records
        self.records = []
        for vm_id in range(0, self.num_vms):
            self.records.append([])

    def connect_client(self):
        debug = False
        self.records = [[]] * self.num_vms
        for vm in self.vms:
            self.records[vm.vm_id] = []
            if not debug:
                self.force_cmd(vm.vm_id)
                time.sleep(3) #important
            else:
                self.vms[vm.vm_id].set_port(12345)
            vm.connect()

    def connect_close(self):
        for vm in self.vms:
            vm.send('all_end:0')
        time.sleep(0.2)
        for vm_id in range(0, self.num_vms):
            self.vms[vm_id].client_close()

    def preprocess(self, task_name = None):
        time.sleep(1)
        for vm in self.vms:
            self.bench_id = vm.bench_id
            vm_id = vm.vm_id
            if self.metric_set_mode:
                self.set_cores(vm.vm_id, vm.num_cores, vm.begin_core)

                rdt = RDT()
                rdt.set_llc_range(self, vm_id, vm.llc_ways_beg, vm.llc_ways_end)
                rdt.set_mb(self, vm_id, vm.memb)

            if self.mode == 'num_cores' or self.mode == 'begin_cores':
                vm.client.send('tasks:0,num_cores:%d,task_name:%s' % (vm.num_cores, self.benchs[self.bench_id]))
            elif self.mode == 'super_share' or self.mode == 'share_llc' or self.mode == 'test_benchmark' or self.mode == 'llc' or self.mode == 'memb':
                vm.client.send('limited_time:0,num_cores:%d,task_name:%s' % (vm.num_cores, self.benchs[self.bench_id]))
            elif self.mode == 'tailbench':
                if task_name:
                    self.bench_id = self.benchs.index(taskname)
                vm.client.send('tasks:0,num_cores:%d,task_name:tailbench.%s,qps:%d,reqs:%d,warmupreqs:%d' % (vm.num_cores, self.benchs[self.bench_id], self.max_qps[self.bench_id], self.ranges[self.bench_id][3], self.ranges[self.bench_id][4]))
            elif self.mode == 'parsec':
                vm.client.send('tasks:0,num_cores:%d,task_name:%s,scale:native,threads:%d,times:%d' % (vm.num_cores, self.benchs[self.bench_id], 16, 1))

        time.sleep(1)
        self.record = [None] * self.num_vms
        num_sample = 1
        if self.metric_set_mode:
            res = self.get_metrics(num_sample)
        for vm in self.vms:
            vm_id = vm.vm_id
            self.record[vm_id] = []
            self.record[vm_id].append(vm_id)
            self.record[vm_id].append(vm.bench_id)
            self.record[vm_id].append(self.benchs[vm.bench_id])
            self.record[vm_id].append(vm.begin_core)
            self.record[vm_id].append(vm.num_cores)
            self.record[vm_id].append(vm.llc_ways_beg)
            self.record[vm_id].append(vm.llc_ways_end)
            self.record[vm_id].append(vm.memb)
            if self.metric_get_mode:
                res_vm = self.vm_metrics(vm_id, num_sample, res)
                for r_vm in res_vm:
                    self.record[vm_id].append(r_vm)
            else:
                for r_vm in [0, 0, 0, 0, 0, 0, 0]:
                    self.record[vm_id].append(r_vm)

    def postprocess(self, data):
        data_dir = 'records'
        for vm in self.vms:
            vm.data = data[vm.vm_id]['res']

        for vm in self.vms:
            vm_id = vm.vm_id
            data = float(vm.data)
            vm.print('avg_perf: %f' % data)
            self.record[vm_id].append(data)

            exp = Exp(self, self.record[vm_id])
            exp.print_title(vm_id)
            exp.print(vm_id)

        res = []
        for j in range(0, self.num_vms):
            res.append(self.record[j])
        for vm in self.vms:
            vm_id = vm.vm_id
            self.records[vm_id].append(res)
            f = open('%s/%03d_%03d_%03d_%s.log' % (data_dir, vm_id, self.run_index, vm.bench_id, self.benchs[vm.bench_id]), 'wb')
            pickle.dump(self.records[vm_id], f)
            f.close()
        VMM.visited = [False] * VMM.N_CORE
        self.maps_vm_core = bidict()

    def init_benchmark(self):
        if self.mode == 'num_cores':
            self.vms[0].num_cores = 4
            self.vms[1].num_cores = VMM.H_CORE - num_cores
            self.vms[0].begin_core = 0
            self.vms[1].begin_core = 0
            self.vms[0].bench_id = self.run_index
            self.vms[1].bench_id = self.run_index
        elif self.mode == 'tailbench':
            self.vms[0].num_cores = 1
            self.vms[0].begin_core = 0
            self.vms[0].bench_id = self.run_index
        elif self.mode == 'parsec':
            self.vms[0].num_cores = 1
            self.vms[0].begin_core = 0
            self.vms[0].bench_id = self.run_index
        elif self.mode == 'begin_core':
            self.vms[0].num_cores = 64
            self.vms[1].num_cores = VMM.H_CORE - num_cores
            self.vms[0].begin_core = 0
            self.vms[1].begin_core = 0
            self.vms[0].bench_id = self.run_index
            self.vms[1].bench_id = self.run_index
        elif self.mode == 'llc':
            self.vms[0].num_cores = 8
            self.vms[0].begin_core = 0
            self.vms[0].bench_id = self.run_index
            self.vms[0].llc_ways_beg = 0
            self.vms[0].llc_ways_end = 1
            self.vms[0].memb = 100
        elif self.mode == 'memb':
            self.vms[0].num_cores = 4
            self.vms[0].begin_core = 0
            self.vms[0].bench_id = self.run_index
            self.vms[0].llc_ways_beg = 0
            self.vms[0].llc_ways_end = VMM.LLC_MAX
            self.vms[0].memb = 10
        elif self.mode == 'share_llc':
            self.vms[0].num_cores = 4
            self.vms[1].num_cores = 4
            self.vms[0].begin_core = 0
            self.vms[1].begin_core = 0
            self.vms[0].bench_id = self.benchs.index('splash2x.water_spatial')
            self.vms[1].bench_id = self.benchs.index('splash2x.water_spatial')
            self.vms[0].llc_range = 1
            self.vms[1].llc_range = 1
            self.vms[0].llc_ways_beg = 0
            self.vms[0].llc_ways_end = 1
            self.vms[1].llc_ways_beg = 0
            self.vms[1].llc_ways_end = 1
            self.vms[0].memb = 100
            self.vms[1].memb = 100
        elif self.mode == 'super_share':
            self.vms[0].num_cores = 4
            self.vms[1].num_cores = 4
            self.vms[0].begin_core = 0
            self.vms[1].begin_core = 0
            self.vms[0].bench_id = self.benchs.index('splash2x.water_nsquared')
            self.vms[1].bench_id = self.benchs.index('splash2x.water_nsquared')
            self.vms[0].llc_range = VMM.LLC_MAX
            self.vms[1].llc_range = VMM.LLC_MAX
            self.vms[0].llc_ways_beg = random.randint(0, 9) #because 10 can not be used isolatedly
            self.vms[0].llc_ways_end = random.randint(self.vms[0].llc_ways_beg + 1, VMM.LLC_MAX)
            self.vms[1].llc_ways_beg = random.randint(0, 9) #because 10 can not be used isolatedly
            self.vms[1].llc_ways_end = random.randint(self.vms[1].llc_ways_beg + 1, VMM.LLC_MAX)
            self.vms[0].memb = 100
            self.vms[1].memb = 100
        elif self.mode == 'test_benchmark':
            self.vms[0].num_cores = 4
            self.vms[1].num_cores = 4
            self.vms[2].num_cores = 4
            self.vms[3].num_cores = 4
            self.vms[0].begin_core = 0
            self.vms[1].begin_core = 0
            self.vms[2].begin_core = 0
            self.vms[3].begin_core = 0
            self.vms[0].bench_id = self.benchs.index('splash2x.water_nsquared')
            self.vms[1].bench_id = self.benchs.index('splash2x.water_spatial')
            self.vms[2].bench_id = self.benchs.index('splash2x.raytrace')
            self.vms[3].bench_id = self.benchs.index('parsec.freqmine')

            self.vms[4].llc_range = VMM.LLC_MAX
            self.vms[5].llc_range = VMM.LLC_MAX
            self.vms[6].llc_range = VMM.LLC_MAX
            self.vms[7].llc_range = VMM.LLC_MAX
            self.vms[4].memb = 100
            self.vms[5].memb = 100 
            self.vms[6].memb = 100 
            self.vms[7].memb = 100 

            self.vms[4].num_cores = 4
            self.vms[5].num_cores = 4
            self.vms[6].num_cores = 4
            self.vms[7].num_cores = 4
            self.vms[4].begin_core = 0
            self.vms[5].begin_core = 0
            self.vms[6].begin_core = 0
            self.vms[7].begin_core = 0
            self.vms[4].bench_id = self.benchs.index('splash2x.water_nsquared')
            self.vms[5].bench_id = self.benchs.index('splash2x.water_spatial')
            self.vms[6].bench_id = self.benchs.index('splash2x.raytrace')
            self.vms[7].bench_id = self.benchs.index('parsec.freqmine')

            self.vms[4].llc_range = VMM.LLC_MAX
            self.vms[5].llc_range = VMM.LLC_MAX
            self.vms[6].llc_range = VMM.LLC_MAX
            self.vms[7].llc_range = VMM.LLC_MAX
            self.vms[4].memb = 100
            self.vms[5].memb = 100 
            self.vms[6].memb = 100 
            self.vms[7].memb = 100 

    def stage1_init_benchmark(self):
        if self.mode == 'num_cores':
            self.vms[0].num_cores += 4
            self.vms[1].num_cores = VMM.H_CORE - num_cores
        elif self.mode == 'tailbench':
            pass
        elif self.mode == 'parsec':
            pass
        elif self.mode == 'begin_core':
            self.vms[0].begin_core += 4
            self.vms[1].begin_core = 0
        elif self.mode == 'llc':
            self.vms[0].llc_ways_end += 1
        elif self.mode == 'memb':
            self.vms[0].memb += 10
        elif self.mode == 'share_llc':
            self.vms[0].llc_ways_end += 1
            self.vms[1].llc_ways_beg -= 1
        elif self.mode == 'super_share':
            self.vms[0].llc_ways_beg = random.randint(0, 9) #because 10 can not be used isolatedly
            self.vms[0].llc_ways_end = random.randint(self.vms[0].llc_ways_beg + 1, VMM.LLC_MAX)
            self.vms[1].llc_ways_beg = random.randint(0, 9) #because 10 can not be used isolatedly
            self.vms[1].llc_ways_end = random.randint(self.vms[1].llc_ways_beg + 1, VMM.LLC_MAX)

    def stage2_init_benchmark(self):
        if self.mode == 'num_cores':
            self.clear_records() #the old data should be saved!
            self.run_index += 1 #new file
            self.vms[0].num_cores = 4
            self.vms[1].num_cores = VMM.H_CORE - num_cores
            self.vms[0].bench_id = self.run_index
            self.vms[1].bench_id = self.run_index
        elif self.mode == 'tailbench':
            self.clear_records() #the old data should be saved!
            self.run_index += 1 #new file
            self.vms[0].begin_core = 0
            self.vms[0].bench_id = self.run_index
        elif self.mode == 'parsec':
            self.clear_records() #the old data should be saved!
            self.run_index += 1 #new file
            self.vms[0].begin_core = 0
            self.vms[0].bench_id = self.run_index
        elif self.mode == 'begin_core':
            self.clear_records() #the old data should be saved!
            self.run_index += 1 #new file
            self.vms[0].begin_core = 0
            self.vms[0].bench_id = self.run_index
        elif self.mode == 'llc':
            self.clear_records() #the old data should be saved!
            self.run_index += 1 #new file
            self.vms[0].llc_ways_end = 1
            self.vms[0].bench_id = self.run_index
        elif self.mode == 'memb':
            self.clear_records() #the old data should be saved!
            self.run_index += 1 #new file
            self.vms[0].memb = 10
            self.vms[0].bench_id = self.run_index
        elif self.mode == 'share_llc':
            self.clear_records() #the old data should be saved!
            self.run_index += 1 #new file
            self.vms[0].bench_id = self.benchs.index('splash2x.water_spatial')
            self.vms[1].bench_id = self.benchs.index('splash2x.water_spatial')
            self.vms[0].llc_range += 1
            self.vms[1].llc_range += 1
            self.vms[0].llc_ways_beg = 0
            #self.vms[0].llc_ways_end = int(self.vms[0].llc_range / 2)
            self.vms[0].llc_ways_end = 1
            self.vms[1].llc_ways_end = self.vms[1].llc_range
            self.vms[1].llc_ways_beg = self.vms[1].llc_ways_end - self.vms[0].llc_ways_end
        elif self.mode == 'super_share':
            self.clear_records() #the old data should be saved!
            self.run_index += 1 #new file
            self.vms[0].bench_id = self.benchs.index('splash2x.water_nsquared')
            self.vms[1].bench_id = self.benchs.index('splash2x.water_nsquared')
            self.vms[0].llc_ways_beg = random.randint(0, 9) #because 10 can not be used isolatedly
            self.vms[0].llc_ways_end = random.randint(self.vms[0].llc_ways_beg + 1, VMM.LLC_MAX)
            self.vms[1].llc_ways_beg = random.randint(0, 9) #because 10 can not be used isolatedly
            self.vms[1].llc_ways_end = random.randint(self.vms[1].llc_ways_beg + 1, VMM.LLC_MAX)

    def run_benchmark(self, task_name = None):
        cmd = [None] * self.num_vms
        data = [None] * self.num_vms

        for vm in self.vms:
            vm.send('begin:0')
        while True:
            for vm_id in range(0, self.num_vms):
                (cmd[vm_id], data[vm_id]) = decode(self.vms[vm_id].recv())
            if cmd[0] == 'begin':   #Only vm 0 is the master node
                self.preprocess(task_name)
            elif cmd[0] == 'res':
                self.postprocess(data)
                for vm_id in range(0, self.num_vms):
                    self.vms[vm_id].send('end:0')
            elif cmd[0] == 'end':
                break

    def preprocess_single(self, vm_id, task_name = None):
        time.sleep(1)
        vm = self.vms[vm_id]
        self.bench_id = vm.bench_id
        if self.metric_set_mode:
            self.set_cores(vm.vm_id, vm.num_cores, vm.begin_core)

            rdt = RDT()
            rdt.set_llc_range(self, vm_id, vm.llc_ways_beg, vm.llc_ways_end)
            rdt.set_mb(self, vm_id, vm.memb)
        if self.mode == 'tailbench':
            if task_name:
                self.bench_id = self.benchs.index(task_name)
            vm.client.send('tasks:0,num_cores:%d,task_name:tailbench.%s,qps:%d,reqs:%d,warmupreqs:%d' % (vm.num_cores, self.benchs[self.bench_id], self.max_qps[self.bench_id] * self.perc_qps[self.bench_id], self.ranges[self.bench_id][3], self.ranges[self.bench_id][4]))
        elif self.mode == 'parsec':
            if task_name:
                vm.client.send('tasks:0,num_cores:%d,task_name:%s,scale:native,threads:%d,times:%d' % (vm.num_cores, task_name, 16, 1))
            else:
                vm.client.send('tasks:0,num_cores:%d,task_name:%s,scale:native,threads:%d,times:%d' % (vm.num_cores, self.benchs[self.bench_id], 16, 1))

        time.sleep(1)
        if vm_id == 0:
            self.record = [None] * self.num_vms
        num_sample = 1
        if self.metric_set_mode:
            res = self.get_metrics(num_sample)
        self.record[vm_id] = []
        self.record[vm_id].append(vm_id)
        self.record[vm_id].append(vm.bench_id)
        self.record[vm_id].append(self.benchs[vm.bench_id])
        self.record[vm_id].append(vm.begin_core)
        self.record[vm_id].append(vm.num_cores)
        self.record[vm_id].append(vm.llc_ways_beg)
        self.record[vm_id].append(vm.llc_ways_end)
        self.record[vm_id].append(vm.memb)
        if self.metric_get_mode:
            res_vm = self.vm_metrics(vm_id, num_sample, res)
            for r_vm in res_vm:
                self.record[vm_id].append(r_vm)
        else:
            for r_vm in [0, 0, 0, 0, 0, 0, 0]:
                self.record[vm_id].append(r_vm)

    def postprocess_single(self, vm_id, data):
        data_dir = 'records'
        vm = self.vms[vm_id]
        vm.data = data['res']

        vm_id = vm.vm_id
        data = float(vm.data)
        vm.print('avg_perf: %f' % data)
        self.record[vm_id].append(data)

        exp = Exp(self, self.record[vm_id])
        exp.print_title(vm_id)
        exp.print(vm_id)

        res = self.record[vm_id]
        self.records[vm_id].append(res)
        f = open('%s/%03d_%03d_%03d_%s.log' % (data_dir, vm_id, self.run_index, vm.bench_id, self.benchs[vm.bench_id]), 'wb')
        pickle.dump(self.records[vm_id], f)
        f.close()
        if vm_id == 0:
            VMM.visited = [False] * VMM.N_CORE
            self.maps_vm_core = bidict()

    def run_benchmark_single(self, vm_id, once = False, task_name = None, skip_header = False):
        cmd = None
        data = None
        vm = self.vms[vm_id]
        if not skip_header:
            vm.send('begin:0')
        while True:
            (cmd, data) = decode(vm.recv())
            if cmd == 'begin':   #Only vm 0 is the master node
                self.preprocess_single(vm_id, task_name)
            elif cmd == 'res':
                self.postprocess_single(vm_id, data)
                vm.send('end:0')
            elif cmd == 'end':
                break
            if once:
                break

    def pre_test_benchmark(self):
        #new VMs
        num_vms = 8
        for vm_id in range(0, num_vms):
            vm_name = 'centos8_test%d' % vm_id
            self.new_vm(vm_id, vm_name)

        self.connect_client()
        self.init_mode('test_benchmark')

    def test_benchmark(self, llc_ways_list):
        for vm in self.vms:
            vm.llc_ways_beg = llc_ways_list[vm.vm_id][0]
            vm.llc_ways_end = llc_ways_list[vm.vm_id][1]

        self.clear_records()
        self.init_benchmark()
        self.run_benchmark()
        self.run_index += 1

        ipcs = []
        for vm_id in range(0, self.num_vms):
            ipcs.append(self.records[0][0][vm_id][10])
        return ipcs

    def aft_test_benchmark(self):
        self.connect_close()

    def read_records(self, data_dir, is_print = True):
        files = os.listdir(data_dir)
        vm_id = 0
        f_list = find_list('^%03d_.*' % vm_id, files)
        print('f_list =', f_list)
        records_total = []
        for run_index in range(0, len(f_list)):
            vm = self.vms[vm_id]
            pat2 = '(^%03d_%03d_.*_.*\..*\.log)' % (vm_id, run_index)
            pat = re.compile(pat2)
            file_name = ''
            for f in files:
                if pat.findall(f):
                    file_name = f
                    print(f)
                    break
            f = open('%s/%s' % (data_dir, file_name), 'rb')
            #f2 = open('%s/%s' % ('records_llc_2', file_name), 'wb')
            records = pickle.load(f)
            if is_print:
                vm.print("[%svm_id, bench_id, bench_name, begin_core, num_cores, %s%sllc_ways_beg, llc_ways_end, memb, %s%sfreq_avg, freq_bzy, ipc, miss, LLC, MBL, MBR, %s%stime%s]" % (color.beg1, color.end, color.beg5, color.end, color.beg1, color.end, color.beg5, color.end))
                for record1 in records:
                    for record2 in record1:
                        exp = Exp(vmm, record2)
                        exp.print()
                vm.print('')
            records_total.append(records)
            f.close()
        #for record1 in records:
        #    for record2 in record1:
        #        record2.insert(7, 100)
        #        print(record2)
        #pickle.dump(records, f2)
        #f2.close()
        return records_total

    def pre_draw(self, data_dir, benchs):
        records_total = self.read_records(data_dir, False)
        #records_total = []
        #for bench_id in range(0, len(benchs)):
        #    records_total.append(self.read_records(data_dir, 0, bench_id, False))
        #different benchmarks, different experiments, different vms
        num_benchs = len(records_total)
        num_exps = len(records_total[0])
        num_vms = len(records_total[0][0])
        #print(num_benchs, num_exps, num_vms)
        vms_exps_benchs = []
        for record in records_total:
            vms_exps = []
            for (ind, exp) in enumerate(record):
                vms_exp = []
                for tmp_exp in exp:
                    vm_exp = Exp(vmm, tmp_exp)
                    vms_exp.append(vm_exp)
                vms_exps.append(vms_exp)
            vms_exps_benchs.append(vms_exps)
        return [num_benchs, num_exps, num_vms, vms_exps_benchs]

    def pre_draw_2(self, num_figs):
        figs = []
        axs = []

        for f_id in range(0, num_figs):
            fig, ax = plt.subplots()
            figs.append(fig)
            axs.append(ax)
        return [figs, axs]

    def post_draw(self, num_figs, figs, axs):
        figdir = 'figs'
        for f_id in range(0, num_figs):
            title = '%s-%s' % (ylabels[f_id], xlabels[f_id])
            axs[f_id].set_title(title)
            if xaxis[f_id]:
                axs[f_id].set_xticks(xaxis[f_id])
            axs[f_id].set_xlabel(xlabels[f_id])
            axs[f_id].set_ylabel(ylabels[f_id])
            #axs[f_id].grid('on')
            #plt.legend(loc='lower left')
            #axs[f_id].legend(loc='best')
            #axs[f_id].legend(loc=2, bbox_to_anchor=(1.05,1.0), borderaxespad = 0.) 
            axs[f_id].legend(loc=2, bbox_to_anchor=(1.0, 1.0))
            #size = figs[f_id].get_size_inches()
            #print(size)
            width = 6.4
            height = 4.8
            figs[f_id].set_figwidth(width  * 1.3)
            figs[f_id].tight_layout()
            file_name = "%s/%s.eps" % (figdir, title)
            #file_name = file_name.replace(' ', '_')
            figs[f_id].savefig(file_name, bbox_inches='tight')

    def post_draw_2(self, num_figs, figs, axs):
        figdir = 'figs'
        for f_id in range(0, num_figs):
            title = '%s-%s' % (ylabels[f_id], xlabels[f_id])
            axs[f_id].set_title(title)
            if xaxis[f_id]:
                axs[f_id].set_xticks(xaxis[f_id])
            width = 6.4
            height = 4.8
            figs[f_id].set_figwidth(width * 1.5)
            figs[f_id].set_figheight(height)
            figs[f_id].tight_layout()
            axs[f_id].set_xlabel(xlabels[f_id])
            file_name = "%s/%s.eps" % (figdir, title)
            figs[f_id].savefig(file_name, bbox_inches='tight')

    def force_cmd(self, vm_id):
        vm = self.vms[vm_id]
        vm.get_ip()
        #port = random.randint(12345, 16000)
        port = 12345
        vm.set_port(port)
        cmd = "ssh root@%s 'pkill test_server'" % (vm.ip)
        p = exec_cmd(cmd, vm_id = vm_id)
        #cmd = "ssh root@%s 'cd /root/tailbench/tailbench-v0.9 && ./test_server.py run %d' &> %s.log" % (vm.ip, port, vm.vm_name)
        pwd = os.getcwd()
        cmd = "ssh root@%s 'cd %s && ./test_server.py run %d' &> %s.log" % (vm.ip, pwd, port, vm.vm_name)
        p = exec_cmd(cmd, 10 + vm_id, False, vm_id = vm_id)
        #vm.print(get_res(vm_id))
        self.p = p

def decode(data):
    pairs = data.split(',')
    res_dict = {}
    for pair in pairs:
        (first, second) = pair.split(':')
        res_dict[first] = second
    cmd = pairs[0].split(':')[0]
    return cmd, res_dict

class SST:
    def __init__(self):
        pass

    def tf(self, num):
        cmd = 'intel-speed-select --cpu 0-%d turbo-freq enable -a' % (num - 1)
        exec_cmd(cmd)

    def tf_close(self):
        cmd = 'intel-speed-select turbo-freq disable -a'
        exec_cmd(cmd)

    def bf(self, num):
        cmd = 'intel-speed-select base-freq enable -a' 
        exec_cmd(cmd)

    def test(self):
        prog = 'intel-speed-select'
        high_cores = 8
        total_cores = 36
        for ind in range(0, high_cores):
            cmd = '%s core-power --cpu %d assoc --clot 0' % (prog, ind)
            exec_cmd(cmd)

        for ind in range(high_cores, total_cores):
            cmd = '%s core-power --cpu %d assoc --clot 3' % (prog, ind)
            exec_cmd(cmd)

class RDT:
    def __init__(self):
        pass

    def range2bit(self, beg, end):
        llc_ways = 0x0
        for way_id in range(beg, end):
            llc_ways |= (1 << way_id)
        return llc_ways

    def list2bit_list(self, lst):
        bit_list = [0] * VMM.LLC_MAX
        for way_id in lst:
            bit_list[way_id] = 1
        return bit_list

    def bit_list2list(self, bit_list):
        lst = []
        for (way_id, bit) in enumerate(bit_list):
            if bit == 0x1:
                lst.append(way_id)
        return lst

    def list2bit(self, lst):
        llc_ways = 0x0
        for way_id in lst:
            llc_ways |= (1 << way_id)
        return llc_ways

    def bit2list(self, bit):
        lst = []
        cnt = 0
        while not bit == 0:
            if bit & 0x1 == 0x1:
                lst.append(cnt)
            bit = bit >> 1
            cnt += 1
        return lst

    def bit_list2bit(self, bit_list):
        llc_ways = 0x0
        for (way_id, bit) in enumerate(bit_list):
            llc_ways |= (bit << way_id)
        return llc_ways

    def bit2bit_list(self, bit):
        bit_list = []
        while not bit == 0:
            if bit & 0x1 == 0x1:
                bit_list.append(1)
            else:
                bit_list.append(0)
            bit = bit >> 1
        while len(bit_list) < VMM.LLC_MAX:
            bit_list.append(0)
        return bit_list

    def set_llc_range(self, vmm, vm_id, way_beg, way_end):
        llc_ways = self.range2bit(way_beg, way_end)
        self.set_llc(vmm, vm_id, llc_ways)

    def set_llc_list(self, vmm, vm_id, lst):
        llc_ways = self.list2bit(lst)
        self.set_llc(vmm, vm_id, llc_ways)

    def set_llc_bitlist(self, vmm, vm_id, bit_list):
        llc_ways = self.bit_list2bit(bit_list)
        self.set_llc(vmm, vm_id, llc_ways)

    def set_llc(self, vmm, vm_id, llc_ways):
        core_list = []
        for core_id in range(0, vmm.vms[vm_id].num_cores):
            core_list.append(str(vmm.maps_vm_core[(vm_id, core_id)]))
        core_list = ",".join(core_list)
        cmd1 = 'pqos -e "llc:%d=0x%x"' % (vm_id + 1, llc_ways)
        cmd2 = 'pqos -a "core:%d=%s"' % (vm_id + 1, core_list)
        print(cmd1)
        print(cmd2)
        exec_cmd(cmd1)
        exec_cmd(cmd2)

    def set_mb(self, vmm, vm_id, mba_perc):
        core_list = []
        for core_id in range(0, vmm.vms[vm_id].num_cores):
            core_list.append(str(vmm.maps_vm_core[(vm_id, core_id)]))
        core_list = ",".join(core_list)
        cmd1 = 'pqos -e "mba:%d=%d"' % (vm_id + 1, mba_perc)
        cmd2 = 'pqos -a "core:%d=%s"' % (vm_id + 1, core_list)
        exec_cmd(cmd1)
        exec_cmd(cmd2)

    def reset(self):
        cmd = 'pqos -R'
        exec_cmd(cmd)

    def show(self):
        cmd = 'pqos -s'
        exec_cmd(cmd)
        print(get_res())

class Exp:
    vm_id = 0
    bench_id = 0
    bench_name = ''
    begin_core = 0
    num_cores = 0

    llc_ways_beg = 0
    llc_ways_end = 0
    memb = 0

    avg_freq = 0
    bzy_freq = 0
    ipc = 0
    miss = 0
    LLc = 0
    MBL = 0
    MBR = 0

    runtime = 0
    vmm = None
    data = []

    def __init__(self, vmm, data):
        self.vm_id = data[0]
        self.bench_id = data[1]
        self.bench_name = data[2]
        self.begin_core = data[3]
        self.num_cores = data[4]

        self.llc_ways_beg = data[5]
        self.llc_ways_end = data[6]
        self.memb = data[7]

        self.avg_freq = data[8]
        self.bzy_freq = data[9]
        self.ipc = data[10]
        self.miss = data[11]
        self.LLC = data[12]
        self.MBL = data[13]
        self.MBR = data[14]
        self.runtime = data[15]

        self.vmm = vmm
        self.data = data

    def print_title(self, vm_id = 0):
        self.vmm.vms[vm_id].print("[%svm_id, bench_id, bench_name, begin_core, num_cores, %s%sllc_ways_beg, llc_ways_end, memb, %s%sfreq_avg, freq_bzy, %s%sipc%s%s, miss, LLC, MBL, MBR, %s%stime%s]" % (color.beg1, color.end, color.beg5, color.end, color.beg1, color.end, color.beg5, color.end, color.beg1, color.end, color.beg5, color.end))

    def print(self, vm_id = 0):
        self.vmm.vms[vm_id].print("[%s%d, %d, %s, %d, %d, %s%s%d, %d, %d, %s%s%f, %f, %s%s%f, %s%s%f, %f, %f, %f, %s%s%f%s]" % (color.beg6, self.vm_id, self.bench_id, self.bench_name, self.begin_core, self.num_cores, color.end, color.beg5, self.llc_ways_beg, self.llc_ways_end, self.memb, color.end, color.beg6, self.avg_freq, self.bzy_freq, color.end, color.beg5, self.ipc, color.end, color.beg6, self.miss, self.LLC, self.MBL, self.MBR, color.end, color.beg5, self.runtime, color.end))

if __name__ == "__main__":
    param = sys.argv[1]
    vmm = None
    if not param == 'test_benchmark':
        #new vmm
        vmm = VMM()

        #new VMs
        num_vms = 1
        for vm_id in range(0, num_vms):
            vm_name = 'centos8_test%d' % vm_id
            vmm.new_vm(vm_id, vm_name)

    if param == 'init':
        for vm_id in range(0, num_vms):
            vm = vmm.vms[vm_id]
            vm.setvcpus_dyn(1)
            vm.setmem_dyn(4)
            vm.setvcpus_sta(VMM.H_CORE)
            vm.setmem_sta(8)
            vm.shutdown()
            time.sleep(10)
            vm.start()
            time.sleep(20)
            vm.setvcpus_dyn(1)
            vm.setmem_dyn(4)
    elif param == 'core':
        for vm_id in range(0, num_vms):
            num_cores = 4
            vmm.set_cores(vm_id, num_cores)
            vmm.set_mem(vm_id, 64)
    elif param == 'start' or param == 'shutdown':
        for vm_id in range(0, num_vms):
            vm = vmm.vms[vm_id]
            if param == 'start':
                vm.start()
            elif param == 'shutdown':
                vm.shutdown()
    elif param == 'ip':
        for vm_id in range(0, num_vms):
            vm = vmm.vms[vm_id]
            vm.get_ip()
    elif param == 'test':
        vm_id = 0
        vmm.set_cores(vm_id, VMM.H_CORE)
        vmm.set_mem(vm_id, 16)
        res = vmm.get_metrics(num)
        vmm.vm_metrics(vm_id, 6, res)
    elif param == 'read':
        #data_dir = 'records_20211123_one_vm_perf_thread'
        data_dir = ''
        if len(sys.argv) >= 3:
            data_dir = sys.argv[2]
        else:
            data_dir = 'records'
        vmm.read_records(data_dir)
    elif param == 'draw':
        if len(sys.argv) >= 3:
            data_dir = sys.argv[2]
        else:
            data_dir = 'records'
        [num_benchs, num_exps, num_vms, vms_exps_benchs] = vmm.pre_draw(data_dir, vmm.benchs)
        num_figs = 3
        xlabels = ['LLC ways', 'LLC ways', 'LLC ways']
        ylabels = ['IPC', 'Run Time(s)', 'MBL']
        xaxis = [range(0, 12, 1), range(0, 12, 1), None]
        [figs, axs] = vmm.pre_draw_2(num_figs)

        for id_bench in range(0, num_benchs):
            num_cores = []
            bzy_freq = []
            runtime = []
            llc_ways = []
            ipc = []
            MBL = []
            for id_exp in range(0, num_exps):
                for id_vm in range(0, 1):
                    ele = vms_exps_benchs[id_bench][id_exp][id_vm]
                    num_cores.append(ele.num_cores)
                    bzy_freq.append(ele.bzy_freq)
                    ipc.append(ele.ipc)
                    MBL.append(ele.MBL)
                    llc_ways.append(ele.llc_ways_end)
                    runtime.append(ele.runtime)
                    if id_exp == num_exps - 1:
                        ratio = (runtime[0] - runtime[id_exp]) / runtime[0] * 100
                        if ratio > 15:
                            print('cbw llc %s%s%s runtime[%d]: %f %f, %f%%' % (color.beg1, ele.bench_name, color.end, id_exp, runtime[0], runtime[id_exp], ratio))
                        else:
                            print('cbw no-llc %s%s%s runtime[%d]: %f %f, %f%%' % (color.beg2, ele.bench_name, color.end, id_exp, runtime[0], runtime[id_exp], ratio))
                    ele.print()
            #axs[0].plot(num_cores, bzy_freq, label = vms_exps_benchs[id_bench][0][0].bench_name)
            #axs[1].plot(num_cores, runtime, label = vms_exps_benchs[id_bench][0][0].bench_name)
            #axs[2].plot(bzy_freq, runtime, label = vms_exps_benchs[id_bench][0][0].bench_name)
            axs[0].plot(llc_ways, ipc, label = vms_exps_benchs[id_bench][0][0].bench_name)
            axs[1].plot(llc_ways, runtime, label = vms_exps_benchs[id_bench][0][0].bench_name)
            axs[2].plot(llc_ways, MBL, label = vms_exps_benchs[id_bench][0][0].bench_name)
            vmm.post_draw(num_figs, figs, axs)

        data_dir = 'records_memb_04cores'
        [num_benchs, num_exps, num_vms, vms_exps_benchs] = vmm.pre_draw(data_dir, vmm.benchs)
        num_figs = 2
        xlabels = ['Memory Bandwidth(%)', 'Memory Bandwidth(%)']
        ylabels = ['IPC', 'Run Time(s)']
        xaxis = [range(0, 110, 10), range(0, 110, 10), None]
        [figs, axs] = vmm.pre_draw_2(num_figs)

        for id_bench in range(0, num_benchs):
            num_cores = []
            bzy_freq = []
            runtime = []
            memb = []
            ipc = []
            for id_exp in range(0, num_exps):
                for id_vm in range(0, 1):
                    ele = vms_exps_benchs[id_bench][id_exp][id_vm]
                    num_cores.append(ele.num_cores)
                    bzy_freq.append(ele.bzy_freq)
                    ipc.append(ele.ipc)
                    memb.append(ele.memb)
                    runtime.append(ele.runtime)
                    if id_exp == num_exps - 1:
                        ratio = (runtime[0] - runtime[id_exp]) / runtime[0] * 100
                        if ratio > 15:
                            print('cbw memb %s%s%s runtime[%d]: %f %f, %f%%' % (color.beg3, ele.bench_name, color.end, id_exp, runtime[0], runtime[id_exp], ratio))
                        else:
                            print('cbw no-memb %s%s%s runtime[%d]: %f %f, %f%%' % (color.beg4, ele.bench_name, color.end, id_exp, runtime[0], runtime[id_exp], ratio))
                    ele.print()
            #axs[0].plot(num_cores, bzy_freq, label = vms_exps_benchs[id_bench][0][0].bench_name)
            #axs[1].plot(num_cores, runtime, label = vms_exps_benchs[id_bench][0][0].bench_name)
            #axs[2].plot(bzy_freq, runtime, label = vms_exps_benchs[id_bench][0][0].bench_name)
            axs[0].plot(memb, ipc, label = vms_exps_benchs[id_bench][0][0].bench_name)
            axs[1].plot(memb, runtime, label = vms_exps_benchs[id_bench][0][0].bench_name)
            vmm.post_draw(num_figs, figs, axs)

        ##plt.show()

    elif param == 'draw_2':
        if len(sys.argv) >= 3:
            data_dir = sys.argv[2]
        else:
            data_dir = 'records'
        [num_benchs, num_exps, num_vms, vms_exps_benchs] = vmm.pre_draw(data_dir, vmm.benchs)
        num_figs = 1
        xlabels = ['LLC way', 'LLC way']
        ylabels = ['IPC', 'Run Time(s)']
        xaxis = [range(0, 12, 1), range(0, 12, 1), None]
        [figs, axs] = vmm.pre_draw_2(num_figs)

        ipc_max = 0
        ipc_min = 2**10
        for id_bench in range(0, num_benchs):
            ipc = []
            for id_exp in range(0, num_exps):
                for id_vm in range(0, 1):
                    ele = vms_exps_benchs[id_bench][id_exp][id_vm]
                    ipc.append(ele.ipc)
            ipc_ratio = [item / ipc[0] for item in ipc]
            print(ipc_ratio)
            if id_bench != 1:
                ipc_min = min(ipc_min, min(ipc_ratio))
                ipc_max = max(ipc_max, max(ipc_ratio))
        print('ipc_min', ipc_min, 'ipc_max', ipc_max)
        c_max = 1.0
        c_min = 0.5
        for id_bench in range(0, num_benchs):
            llc_ways = []
            ipc = []
            for id_exp in range(0, num_exps):
                for id_vm in range(0, 1):
                    ele = vms_exps_benchs[id_bench][id_exp][id_vm]
                    ipc.append(ele.ipc)
                    llc_ways.append(ele.llc_ways_end)
            ipc_ratio = [item / ipc[0] for item in ipc]
            for (ind, item) in enumerate(ipc_ratio):
                if item > ipc_max:
                    ipc_ratio[ind] = ipc_max
            color_value = transform_list(ipc_ratio, ipc_min, ipc_max, c_min, c_max)
            #print('color_value', color_value)
            color_value_2 = cvalue_list(color_value)
            print('color_value_2', color_value_2)
            for id_exp in range(0, num_exps):
                axs[0].add_patch(
                                patches.Rectangle(
                                (id_exp, id_bench),   # (x,y)
                                1,          # width
                                1,          # height
                                color=color_value_2[id_exp])
                            )
        layers = 20
        height_layer = 0.2
        ele = vms_exps_benchs[0][-1][0]
        x_max = ele.llc_ways_end 
        rect_x = x_max + 1.0
        rect_y = 2
        rect_w = 0.5
        rect_h = height_layer * layers
        for i in range(0, layers):
            j = i / (layers - 1)
            axs[0].add_patch(
                            patches.Rectangle(
                            (rect_x, rect_y + height_layer * i),   # (x,y)
                            rect_w,          # width
                            height_layer,          # height
                            color=cvalue((c_max - c_min) * j + c_min))
                        )
        axs[0].add_patch(
                        patches.Rectangle(
                        (rect_x, rect_y),   # (x,y)
                        rect_w,          # width
                        rect_h,          # height
                        edgecolor = '#000000', facecolor = 'None')
                    )
        axs[0].set_xlim(0, x_max + 2.5)
        axs[0].set_ylim(0, num_benchs)
        axs[0].set_ylabel('Benchmark')
        axs[0].set_yticks([item + 0.5 for item in list(range(0, len(vmm.benchs)))])
        axs[0].set_yticklabels(vmm.benchs)
        axs[0].text(rect_x + rect_w / 2, rect_y - 0.5, s = '%0.2f%%' % (ipc_min * 100), ha = 'center', va = 'center')
        axs[0].text(rect_x + rect_w / 2, rect_y + height_layer * layers + 0.5, s = '%0.2f%%' % (ipc_max * 100), ha = 'center', va = 'center')
        vmm.post_draw_2(num_figs, figs, axs)
    elif param == 'draw_3':
        if len(sys.argv) >= 3:
            data_dir = sys.argv[2]
        else:
            data_dir = 'records'
        [num_benchs, num_exps, num_vms, vms_exps_benchs] = vmm.pre_draw(data_dir, vmm.benchs)
        num_figs = 1
        xlabels = ['Memory Bandwidth', 'Memory Bandwidth']
        ylabels = ['IPC', 'Run Time(s)']
        xaxis = [range(0, 11, 1), range(0, 11, 1), None]
        [figs, axs] = vmm.pre_draw_2(num_figs)

        ipc_max = 0
        ipc_min = 2**10
        for id_bench in range(0, num_benchs):
            ipc = []
            for id_exp in range(0, num_exps):
                for id_vm in range(0, 1):
                    ele = vms_exps_benchs[id_bench][id_exp][id_vm]
                    ipc.append(ele.ipc)
            ipc_ratio = [item / ipc[0] for item in ipc]
            print(ipc_ratio)
            if id_bench != 1:
                ipc_min = min(ipc_min, min(ipc_ratio))
                ipc_max = max(ipc_max, max(ipc_ratio))
        print('ipc_min', ipc_min, 'ipc_max', ipc_max)
        c_max = 1.0
        c_min = 0.5
        for id_bench in range(0, num_benchs):
            llc_ways = []
            ipc = []
            for id_exp in range(0, num_exps):
                for id_vm in range(0, 1):
                    ele = vms_exps_benchs[id_bench][id_exp][id_vm]
                    ipc.append(ele.ipc)
            ipc_ratio = [item / ipc[0] for item in ipc]
            for (ind, item) in enumerate(ipc_ratio):
                if item > ipc_max:
                    ipc_ratio[ind] = ipc_max
            color_value = transform_list(ipc_ratio, ipc_min, ipc_max, c_min, c_max)
            #print('color_value', color_value)
            color_value_2 = cvalue_list(color_value)
            print('color_value_2', color_value_2)
            for id_exp in range(0, num_exps):
                axs[0].add_patch(
                                patches.Rectangle(
                                (id_exp, id_bench),   # (x,y)
                                1,          # width
                                1,          # height
                                color=color_value_2[id_exp])
                            )
        layers = 20
        height_layer = 0.2
        ele = vms_exps_benchs[0][-1][0]
        x_max = int(ele.memb / 10)
        rect_x = x_max + 1.0
        rect_y = 2
        rect_w = 0.5
        rect_h = height_layer * layers
        for i in range(0, layers):
            j = i / (layers - 1)
            axs[0].add_patch(
                            patches.Rectangle(
                            (rect_x, rect_y + height_layer * i),   # (x,y)
                            rect_w,          # width
                            height_layer,          # height
                            color=cvalue((c_max - c_min) * j + c_min))
                        )
        axs[0].add_patch(
                        patches.Rectangle(
                        (rect_x, rect_y),   # (x,y)
                        rect_w,          # width
                        rect_h,          # height
                        edgecolor = '#000000', facecolor = 'None')
                    )
        axs[0].set_xlim(0, x_max + 2.5)
        axs[0].set_ylim(0, num_benchs)
        axs[0].set_ylabel('Benchmark')
        axs[0].set_yticks([item + 0.5 for item in list(range(0, len(vmm.benchs)))])
        axs[0].set_xticklabels(['%d%%' % int(item) for item in list(range(0,110,10))])
        axs[0].set_yticklabels(vmm.benchs)
        axs[0].text(rect_x + rect_w / 2, rect_y - 0.5, s = '%0.2f%%' % (ipc_min * 100), ha = 'center', va = 'center')
        axs[0].text(rect_x + rect_w / 2, rect_y + height_layer * layers + 0.5, s = '%0.2f%%' % (ipc_max * 100), ha = 'center', va = 'center')
        vmm.post_draw_2(num_figs, figs, axs)
    elif param == 'run':
        vmm.connect_client()

        #vmm.init_mode('begin_core')
        #vmm.init_mode('num_cores')
        #vmm.init_mode('llc')
        #vmm.init_mode('memb')
        #vmm.init_mode('share_llc')
        #vmm.init_mode('super_share')
        vmm.init_mode('tailbench')
        #vmm.init_mode('parsec')

        vmm.init_benchmark()
        print('vmm.num_vms = ', vmm.num_vms)
        while True:
            vmm.run_benchmark()
            if vmm.end_stage1(vmm.vms[0].num_cores, vmm.vms[0].begin_core):
                if vmm.end_stage2():
                    break
                else:
                    vmm.stage2_init_benchmark()
            else:
                vmm.stage1_init_benchmark()
        vmm.connect_close()

    elif param == 'test_benchmark':
        #new vmm
        vmm = VMM()

        num_vms = 2
        llc_ways_list = []
        for vm_id in range(0, num_vms):
            llc_ways = []
            t = random.randint(0, 9)
            llc_ways.append(t) #because 10 can not be used isolatedly
            llc_ways.append(random.randint(t + 1, VMM.LLC_MAX))
            llc_ways_list.append(llc_ways)
        print(llc_ways_list)
        vmm.pre_test_benchmark()
        vmm.test_benchmark(llc_ways_list)
        llc_ways_list[0][0] = 0
        llc_ways_list[0][1] = VMM.LLC_MAX
        vmm.test_benchmark(llc_ways_list)
        llc_ways_list[0][0] = 5
        llc_ways_list[0][1] = 7
        llc_ways_list[1][0] = 4
        llc_ways_list[1][1] = 9
        vmm.test_benchmark(llc_ways_list)
        vmm.aft_test_benchmark()

    elif param == 'sst':
        sst = SST()
        #sst.test()
        sst.tf(4) #num is the number of physical cores
    elif param == 'rdt':
        rdt = RDT()
        num_cores = 4
        vmm.set_cores(0, num_cores)
        vmm.set_cores(1, num_cores)
        rdt.set_llc_range(vmm, 0, 8, 8)
        rdt.set_llc_range(vmm, 1, 8, 8)
        #rdt.set_mb(vmm, 0, 30)
        #rdt.set_mb(vmm, 1, 50)
        #rdt.set_llc_bitlist(vmm, 0, [1, 1, 1, 0,   0, 0, 0, 0,   0, 0, 0])
        #rdt.set_llc_bitlist(vmm, 1, [0, 0, 0, 1,   1, 1, 0, 0,   0, 0, 0])

        rdt.show()
    elif param == 'clean':
        rdt = RDT()
        rdt.reset()
    elif param == 'spid':
        #print(vmm.vms[0].get_spid())
        num_cores = 8
        vmm.set_cores(0, num_cores)
    elif param == 'ssh':
        vmm.force_cmd(0)
        #vm_id = 0
        #vm = vmm.vms[vm_id]
        #vm.get_ip()
        #p = exec_cmd("ssh -t %s 'cd /root/vm_control/control_exp && ./test_server.py run 12345' > %s.log" % (vm.ip, vm.vm_name), 1, True)
        #ssh = paramiko.SSHClient()
        #ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        #ssh.connect(hostname='192.168.122.169', port=22, username='root', password='123')
        #stdin, stdout, stderr = ssh.exec_command('cd /root/vm_control/control_exp && ./test_server.py run 12345')
        #print(stdout.read())
        #print(stderr.read())
    elif param == 'sync_file':
        option == sys.argv[2]
        sync_file(option)
    else:
        print("param error")
