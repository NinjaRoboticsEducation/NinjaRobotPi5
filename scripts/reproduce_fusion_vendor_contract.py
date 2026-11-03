"""Reproduce pinned Fusion driver contract failures with simulated I/O only.

Usage: python scripts/reproduce_fusion_vendor_contract.py /path/to/fusion-hat
The source checkout is read, never built, installed or modified. Requires cc.
Exit zero means the documented failures were reproduced, NOT driver acceptance.
"""

import argparse
import hashlib
import json
import re
import subprocess
import tempfile
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("source", type=Path)
parser.add_argument("--patched", action="store_true", help="Validate repaired contracts")
args = parser.parse_args()
SOURCE = args.source / "driver"
EXPECTED = {
    "pwm.c": "4ec8c3c67bdccee98abb80fdc10a80c6fee6af06506c60c6b8a68e2739d7891b",
    "battery.c": "4c17947a5e1f376d790db5e96c90eab0f8f10d9d50b9aa9c41e5e20f1168c8df",
}
if args.patched:
    manifest = json.loads(
        (Path(__file__).resolve().parents[1] / "vendor/fusion-hat/manifest.json").read_text()
    )
    EXPECTED = {name: manifest["files"]["driver/" + name]["patched"] for name in EXPECTED}
for filename, expected in EXPECTED.items():
    if hashlib.sha256((SOURCE / filename).read_bytes()).hexdigest() != expected:
        parser.error(f"{filename}: source differs from reviewed pin; refusing to execute harness")


def function(file, name):
    s = (SOURCE / file).read_text()
    m = re.search(r"^(?:static )?(?:void|int|ssize_t) " + name + r"\(", s, re.M)
    assert m
    start = s.index("{", m.start())
    level = 1
    end = start + 1
    while level:
        if s[end] == "{":
            level += 1
        elif s[end] == "}":
            level -= 1
        end += 1
    return s[m.start() : end]


battery = (SOURCE / "battery.c").read_text()
props = sorted(set(re.findall(r"\bPOWER_SUPPLY_[A-Z_]+", battery)))
preamble = r"""
#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/types.h>
#include <errno.h>
#define mutex_lock(x) ((void)0)
#define mutex_unlock(x) ((void)0)
#define dev_err(...) ((void)0)
#define printk(...) ((void)0)
#define KERN_INFO ""
#define CMD_READ_BATTERY_H 0x18
#define CMD_READ_CHARGING_STATUS 0
#define ADC_REFERENCE_VOLTAGE 3300
#define ADC_MAX_VALUE 4095
#define BATTERY_DIVIDER 3
#define BATTERY_MIN_VOLTAGE 6000
#define BATTERY_MAX_VOLTAGE 8400
#define PWM_DEFAULT_PERIOD 20000
#define BATTERY_MAX_AGE_MS 3000
#define msecs_to_jiffies(x) (x)
#define time_after(a,b) ((long)((b)-(a)) < 0)
static unsigned long jiffies;
struct i2c_client {int dev;};
struct power_supply {void *data;};
struct fusion_hat_dev {
 int lock; struct i2c_client *client; struct power_supply *battery;
 int battery_voltage,battery_level; bool charging;
 bool battery_valid; unsigned long battery_sample_jiffies;
 int pwm_errors[12];
 bool pwm_enabled[12]; uint32_t pwm_periods[12],pwm_duty_cycles[12];
};
struct fusion_hat_dev *fusion_dev;
struct kobject {int unused;}; struct kobj_attribute {int unused;};
struct fusion_hat_pwm_channel {struct kobject kobj; int channel; struct fusion_hat_dev *dev;};
#define container_of(ptr,type,member) ((type *)((char *)(ptr)-offsetof(type,member)))
static int fail_bus, last_pulse;
static int fusion_hat_i2c_read_word(struct i2c_client *c,int reg,uint16_t *v,bool be) {
 if(fail_bus) { return -EIO; }
 *v=3100;return 0;}
static int fusion_hat_i2c_read_byte(struct i2c_client *c,int reg,uint8_t *v) {
 if(fail_bus) { return -EIO; }
 *v=0;return 0;}
static void power_supply_changed(struct power_supply *p) {}
static void *power_supply_get_drvdata(struct power_supply *p) {return p->data;}
union power_supply_propval {int intval;const char *strval;};
static int kstrtou8(const char *s,int base,uint8_t *v) {*v=strtoul(s,0,base);return 0;}
static void fusion_hat_pwm_calc_div(uint32_t p,uint32_t *psc,uint32_t *arr) {*psc=72;*arr=p-1;}
static uint16_t fusion_hat_pwm_calc_compare(uint32_t duty,uint32_t period,uint32_t scale) {
 return duty;}
static int fusion_hat_write_period_value(struct i2c_client *c,int channel,uint16_t value) {
 return fail_bus?-EIO:0;}
static int fusion_hat_write_prescaler_value(struct i2c_client *c,int channel,uint16_t value) {
 return fail_bus?-EIO:0;}
static int fusion_hat_write_pwm_value(struct i2c_client *c,int channel,uint16_t value) {
 if(fail_bus) { return -EIO; }
 last_pulse=value;return 0;}
"""
main = r"""
int main(void) {
 struct i2c_client client={0}; struct fusion_hat_dev dev={.client=&client,.battery_voltage=7500};
 struct power_supply psy={.data=&dev}; union power_supply_propval val;
 fusion_dev=&dev; fail_bus=0;
 fusion_hat_update_battery_status(&dev);
 int healthy=fusion_hat_get_property(&psy,POWER_SUPPLY_PROP_VOLTAGE_NOW,&val);
 printf("successful battery poll: status=%d, voltage_now=%d uV\n",healthy,val.intval);
 if(healthy!=0 || val.intval!=7494000)return 4;
 dev.battery_voltage=7500; fail_bus=1;
 fusion_hat_update_battery_status(&dev);
 int status=fusion_hat_get_property(&psy,POWER_SUPPLY_PROP_VOLTAGE_NOW,&val);
 printf("failed battery poll: get_property status=%d, voltage_now=%d uV\n",status,val.intval);
 if(status!=0 || val.intval!=7500000)return 1;
 struct fusion_hat_pwm_channel chan={.channel=0,.dev=&dev};
 dev.pwm_enabled[0]=true;dev.pwm_periods[0]=20000;dev.pwm_duty_cycles[0]=1500;
 ssize_t result=enable_store(&chan.kobj,0,"0",1);
 printf("failed PWM disable: return=%ld, cached enabled=%d, cached duty=%u us\n",
        (long)result,dev.pwm_enabled[0],dev.pwm_duty_cycles[0]);
 if(result!=1 || dev.pwm_enabled[0] || dev.pwm_duty_cycles[0]!=1500)return 2;
 fail_bus=0;result=enable_store(&chan.kobj,0,"1",1);
 printf("subsequent enable: return=%ld, restored pulse=%d us\n",(long)result,last_pulse);
 if(result!=1 || last_pulse!=1500)return 3;
 puts("Three upstream contract failures reproduced using extracted functions and simulated I/O.");
 return 0;
}
"""
if args.patched:
    main = r"""
int main(void) {
 struct i2c_client client={0}; struct fusion_hat_dev dev={.client=&client};
 struct power_supply psy={.data=&dev}; union power_supply_propval val;
 fusion_dev=&dev;
 if(fusion_hat_get_property(&psy,POWER_SUPPLY_PROP_VOLTAGE_NOW,&val)!=-ENODATA)return 1;
 fusion_hat_update_battery_status(&dev);
 if(fusion_hat_get_property(&psy,POWER_SUPPLY_PROP_VOLTAGE_NOW,&val)||val.intval!=7494000)
   return 2;
 jiffies=3001;
 if(fusion_hat_get_property(&psy,POWER_SUPPLY_PROP_VOLTAGE_NOW,&val)!=-ENODATA)return 3;
 fusion_hat_update_battery_status(&dev);
 if(fusion_hat_get_property(&psy,POWER_SUPPLY_PROP_VOLTAGE_NOW,&val))return 4;
 fail_bus=1;fusion_hat_update_battery_status(&dev);
 if(fusion_hat_get_property(&psy,POWER_SUPPLY_PROP_VOLTAGE_NOW,&val)!=-ENODATA)return 5;
 for(int i=0;i<12;i++) {
   struct fusion_hat_pwm_channel chan={.channel=i,.dev=&dev};
   dev.pwm_enabled[i]=true;dev.pwm_duty_cycles[i]=1500;
   if(enable_store(&chan.kobj,0,"0",1)!=-EIO || !dev.pwm_enabled[i])return 6;
   fail_bus=0;
   if(enable_store(&chan.kobj,0,"0",1)!=1 || dev.pwm_enabled[i] ||
      dev.pwm_duty_cycles[i] || dev.pwm_errors[i])return 7;
   dev.pwm_duty_cycles[i]=1500;
   if(enable_store(&chan.kobj,0,"1",1)!=1 || last_pulse || dev.pwm_duty_cycles[i])return 8;
   fail_bus=1;
 }
 puts("PASS: battery validity, expiry and recovery; all 12 PWM stop errors and zero re-enable.");
 return 0;
}
"""
code = (
    preamble
    + "\nenum power_supply_property {"
    + ",".join(props)
    + "};\n"
    + function("battery.c", "fusion_hat_update_battery_status")
    + "\n"
    + function("battery.c", "fusion_hat_get_property")
    + "\n"
    + function("pwm.c", "enable_store")
    + main
)
with tempfile.TemporaryDirectory() as d:
    p = Path(d)
    (p / "contract.c").write_text(code)
    subprocess.run(
        [
            "cc",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-Wno-unused-parameter",
            "-Wno-unused-function",
            "-Wno-unused-variable",
            str(p / "contract.c"),
            "-o",
            str(p / "contract"),
        ],
        check=True,
        timeout=30,
    )
    subprocess.run([str(p / "contract")], check=True, timeout=30)
