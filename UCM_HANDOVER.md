## 一、项目概述

本项目基于 **Grandstream UCM 系列 IP-PBX** 平台，主要功能为：

* 模拟线路桥接（FXO/FXS）
* VoIP 中继配置（SIP Trunk）
* 呼叫路由（入局 / 出局规则）
* 分机转发规则（转移、随行转接）
* 系统远程管理（GDMS / UCM RemoteConnect）


---

## 二、系统组成

1. **UCM 主机型号**：UCM6302A 系列
2. **模拟接口**：

   * FXO：接入外部 PSTN 公网线路
   * FXS：接入传统模拟电话 / 传真机
3. **VoIP 中继**：

   * 运营商 SIP 账号型中继
   * 对等 SIP Trunk（用于与其他 PBX/网关互联）
4. **分机终端**：

   * SIP IP 电话
   * 模拟电话（FXS 接口）
   * Wave App（PC/移动端）
5. **管理平台**：

   * UCM Web 界面（配置与维护）
   * GDMS 云端管理平台
   * UCM RemoteConnect（远程 NAT 穿透）

---

## 三、主要配置说明

### 1. 模拟桥接

* 在 **PBX → Interfaces → Analog Trunks** 配置 FXO 外线。
* 在 **PBX → Extensions → Analog** 配置 FXS 分机。
* 在 **Inbound Routes** 设置 PSTN 来电去向（分机/IVR）。
* 在 **Outbound Routes** 设置分机呼出规则 → 走 FXO 外线。

### 2. VoIP 桥接

* 在 **PBX → Interfaces → VoIP Trunks** 添加 SIP Trunk。

  * 注册型：填写运营商提供的 SIP 用户名、密码、服务器地址。
  * 对等型：填写远端 IP，不需要账号密码。 重要：本项目使用此类型
* 在 **Outbound Routes** 添加拨号规则（如 9X. → VoIP Trunk）。
* 在 **Inbound Routes** 设置 DID 来电路由。

### 3. 转发规则

* **分机功能码**：

  * \*72 + 号码：无条件转移
  * \*90 + 号码：遇忙转移
  * \*92 + 号码：无应答转移
  * \*73：取消转移
