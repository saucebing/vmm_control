#!/bin/bash
set +x
#file_path=/root/tars/tailbench-v0.9/img-dnn/myrun.sh
#file_path=/root/tars/tailbench-v0.9/masstree/myrun.sh
file_path=/root/tars/parsec-3.0/pkgs/apps/blackscholes/inputs/input_native.tar
src_vm=2
scp test$src_vm:$file_path tmp
for((i=0;$i<3;i+=1));
do
    if(($i != $src_vm)); then
        echo test$i
        scp tmp test$i:$file_path
        ssh test$i "chmod +x $file_path"
    fi
done
