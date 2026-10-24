# 增援耗尽自动播放雨爱

Rainie Love on Reinforcement Depletion · 当前正式版 **v0.2.9**

《绝地潜兵 2》本地音乐 Mod：在任务中增援为零且仅剩一名潜兵存活时，淡入并循环播放 Rainie Love。增援恢复、存活人数变化、登上撤离运输船或对局结束时淡出。

## 功能与安装

- 淡入固定 1 秒；音量 0–100%，默认 50%；淡出时间 1–30 秒，默认 1 秒。
- 通过 Mod Options Menu 提供音量、淡出时间和试听设置；设置修改后需要应用。
- 坦克、机甲、侦察车等普通载具不会触发撤离停播。
- 错过撤离船时，原生任务结束检测负责停播并锁定，下一局开始时重置。
- 单人特殊任务从零增援开局时，首次获得增援后才启用耗尽触发。多人中途加入零增援战斗会直接启用检测。
- MP3 启动时静音预热后暂停；触发时恢复，淡出完成后再次暂停。第一次播放从歌曲开头开始，再次触发从暂停位置继续。

运行需要 **Bingus Shared Loader v15+ / API 1**。Mod Options Menu 是设置界面的可选前置，可使用 Vanilla Plus 内置版本；**不需要 HD2Runtime**。将构建出的 ZIP 导入 Arsenal 或 HD2MM，部署后重启游戏。

源码仓库不包含安装包、歌曲或其他 Mod。项目发布页：[Nexus Mods](https://www.nexusmods.com/helldivers2/mods/16745)。

## 开发文件

```text
src/
  rainie_love.lua.in          原生只读采样、播放后端、菜单与主循环
  mission_boundary.lua       独立任务边界逻辑，构建时嵌入主模块
tools/
  build_release.py           构建 Arsenal/HD2MM 安装包
  run_tests.py               不启动游戏的离线 Lua 检查
tests/
  test_mission_boundary.lua  任务结束、新任务及读取失败测试
  vehicle_seat_fixture.lua   运输船/普通载具组件测试
CHANGELOG.md
THIRD_PARTY.md
```

本地目录可能另存历史原型和诊断工具，已排除在 Git 跟踪之外。当前安装包只使用上述两个正式源文件。

## 从源码构建

需要 Python 3.10+，仅使用标准库，不需要 HD2Runtime SDK 或其他项目目录。

自行准备原版音频后运行：

```powershell
python -B tools/build_release.py --audio "D:\Audio\雨爱DJ.mp3"
```

也可以从已有的本地安装包提取相同音频：

```powershell
python -B tools/build_release.py --from-package "D:\Downloads\Rainie-Love-on-Reinforcement-Depletion-v0.2.9.zip"
```

无参数时优先读取 `assets/audio/雨爱DJ.mp3`，也保留旧工作区音频和 v0.2.7 安装包的本地回退路径。默认输出 `release/Rainie-Love-on-Reinforcement-Depletion-v0.2.9.zip`；用 `--output-dir PATH` 可指定其他目录。`release/` 和音频目录不会上传 Git。

v0.2.9 原始音频固定为 6,319,567 字节，SHA-256：

```text
b0659832d46bd6f3633adac8723c624ccdae8ece72c53e9928a68f476ead314e
```

构建校验音频和 ZIP 完整性，并输出安装包与音频 SHA-256。改用其他音频需要同时调整构建校验及运行时缓存识别，不能直接替换文件。

## 离线验证

在 64 位 Windows/Python 上使用自行安装的游戏 Lua VM：

```powershell
python -B tools/run_tests.py --lua-dll "D:\Steam\steamapps\common\Helldivers 2\bin\lua51.dll"
```

也可设置环境变量 `HD2_LUA51_DLL`。测试仅创建独立 Lua 状态，不连接游戏进程、不读取真实玩家或内存采集数据。

覆盖合成主模块语法、连续任务结束确认、新任务 ID、未知读取不触发结束，以及普通载具/运输船组件边界。离线通过不代表所有多人场景均已实测。

## 原生检测与验证范围

当前字段来自 Steam build 25480438 对应布局。参考 `game.dll` SHA-256：

```text
2e2c3b7c2500646dadd5f2b4c6e0504dbb7e7896139f64cddc0d1813c718f51e
```

运行代码会校验运输船和任务状态相关的指令字节；**未实现所有字段的完整布局校验，也未对 EXE/DLL 做完整文件哈希检查**。游戏更新后需重新核验，不能直接视为兼容。

任务结束按原生游戏状态离开 Mission 判定，连续两个采样确认后锁定。这不是运输船起飞事件，错过撤离时可能在进入结算/返舰阶段才停播。每 0.25 秒采样一次，音量渐变逐帧更新。

已实测普通载具不停播、正常登船淡出，以及一次单人错过撤离后的任务结束锁定。Mod Options Menu 分类切换时的第三行变灰问题仍未解决，已观察到不影响实际操作；正式版不包含此前菜单诊断修改。

## 日志与素材

日志：`%LOCALAPPDATA%\CowboyBingus\Helldivers2\Logs\RainieLove.log`。

仓库不打包研究依赖、DLL、进程内存、个人日志、音频或内嵌歌曲的 ZIP。依赖与素材说明见 [THIRD_PARTY.md](THIRD_PARTY.md)，版本变更见 [CHANGELOG.md](CHANGELOG.md)。
