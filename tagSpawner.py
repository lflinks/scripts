#!/usr/bin/env python

import argparse
import boto3
ec2 = boto3.client("ec2")
asg = boto3.client("autoscaling")
elb = boto3.client("elb")

#parse args
parser = argparse.ArgumentParser(description='input')
mode = parser.add_mutually_exclusive_group()
regex = parser.add_mutually_exclusive_group()
parser.add_argument('-r', '--resources', metavar='S', nargs='+')
parser.add_argument('-t', '--tags', metavar='S', nargs='+')
parser.add_argument('--elb', metavar='S', nargs='+')
parser.add_argument('--asg', metavar='S', nargs='+')
mode.add_argument('--new', action="store_true", dest='mode')
mode.add_argument('--baseTag', metavar='S', nargs=1, dest='mode')
regex.add_argument('--exact', action="store_true")
regex.add_argument('--starts', action="store_true")

#usage
parser.usage="\ntag resources based on resource IDs:\n"
parser.usage+="autoTagging.py --new --resources PHISYCAL_ID_1 .. PHYSICAL_ID_N --tags TAG_KEY_1:TAG_VALUE_1 .. TAG_KEY_N:TAG_VALUE_N\n"
parser.usage+="supports elb with --elb ELB_NAME_1 .. ELB_NAME_N\n"
parser.usage+="supports autoscaling groups with --asg ASG_NAME_1 .. ASG_NAME_N\n\n"

parser.usage+="tag resources based on current tag\n"
parser.usage+="autoTagging.py --baseTag TAG_NAME:TAG_VALUE_SUBSTRING [--exact|--starts] --tags TAG_KEY_1:TAG_VALUE_1 .. TAG_KEY_N:TAG_VALUE_N\n"
parser.usage+="adds the list of TAG_KEY:TAG_VALUE in all resources where TAG_NAME contains the value TAG_VALUE_SUBSTRING\n"
#parser.usage+="with --exact:\n adds the list of TAG_KEY:TAG_VALUE in all resources where TAG_NAME is exactly AG_VALUE_SUBSTRING\n"
#parser.usage+="with --starts:\n adds the list of TAG_KEY:TAG_VALUE in all resources where TAG_NAME starts with TAG_VALUE_SUBSTRING\n\n"

parser.usage+="Examples:\n"
parser.usage+="autoTagging.py --new -r sg-12345678 ami-12345678 --elb my_elb1 other_elb --asg my_app_autoscaling -t Env:prod CostCenter:4001 service:my_app\n"
parser.usage+="autoTagging.py --baseTag Name:production --tags Env:prod\n"
#parser.usage+="autoTagging.py --baseTag Name:APP1_ --starts -t Service:app1 CostCenter:4001\n"


def genTags(tags):
    keys = ["Key", "Value"]
    data = []
    for tag in tags:
        data.append(dict(zip(keys, tag.split(":"))))
    return data

def asgGenTags(asgs, tags):
    data = []
    for asg in asgs:
        tagList = genTags(tags)
        for tag in tagList:
            tag['ResourceId']=asg
            tag['PropagateAtLaunch']=bool(1)
            tag['ResourceType']= 'auto-scaling-group'
        data += tagList
    return data

def usage(opt):
    if opt == "mode":
        return parser.usage + "\nYou need to select one between \"--new\" and \"--baseTag\""
    return parser.usage

def _sgMatches(key, nameRegex):
    toTag = []
    sgList = ec2.describe_security_groups()
    for sg in sgList['SecurityGroups']:
        try:
            for tag in sg['Tags']:
                print tag
                if tag['Key'] == key and nameRegex in tag['Value']:
                    toTag.append(sg['GroupId'])
        except:
            pass
    return toTag

def _amiMatches(key, nameRegex):
    toTag = []
    amiList = ec2.describe_images(Owners=['self'])
    for ami in amiList['Images']:
        try:
            tags = ami['Tags']
            for tag in tags:
                if tag['Key'] == key and nameRegex in tag['Value']:
                    toTag.append(ami['ImageId'])
        except:
            pass
    return toTag

def _ec2Matches(key, nameRegex):
    toTag = []
    ec2List = ec2.describe_instances()['Reservations']
    for ec2Instances in ec2List:
        for ec2Instance in ec2Instances['Instances']:
            try:
                for tag in ec2Instance['Tags']:
                    if tag['Key'] == key and nameRegex in tag['Value']:
                        toTag.append(ec2Instance['InstanceId'])
            except:
                pass
    return toTag

def getMatches(key, nameRegex):
    toTag = _ec2Matches(key, nameRegex)
    toTag += _amiMatches(key, nameRegex)
    toTag += _sgMatches(key, nameRegex)
    print toTag
    return filter(None, toTag)

if __name__ == '__main__':
    args = parser.parse_args()
    tags = args.tags
    mode = args.mode
    res = False
    elbNames = False
    asgNames = False
    regex = False

    if not tags:
        raise Exception(usage("full"))
    if not mode:
        raise Exception(usage("mode"))

    if mode == bool(1):
        mode = False
        res = args.resources
        elbNames = args.elb
        asgNames = args.asg

    if args.starts:
        regex = "st"
    if args.exact:
        regex = "ex"

    tagList = genTags(tags)
    if mode:
        res = getMatches(*mode[0].split(":"))

    if res:
        ec2.create_tags(Resources=res, Tags=tagList)
    if elbNames:
        elb.add_tags(LoadBalancerNames=elbNames, Tags=tagList)
    if asgNames:
        asgTags = asgGenTags(asgNames, tags)
        asg.create_or_update_tags(Tags=asgTags)

