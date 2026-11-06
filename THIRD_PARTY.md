# 外部组件与素材

- **MDL3 / HD2 Data Hub**：MDL v0.3.0 实现使用公开生命周期、音频 API 和 HD2Data 只读接口。作者为 M!ni$try0fSc!eиce；请自行从 [官方发布页](https://ayakamods.com/mods/mdl3-preview-%E9%BA%A6%E5%BD%93%E5%8A%B33-%E9%A2%84%E8%A7%88%E7%89%88%EF%BC%81.5710/) 阅读说明并下载。此分支不包含这些组件或其实现代码。
- **FFmpeg**：本地构建时调用 FFmpeg 转换原曲为 PCM，再由本项目独立编码为 MS-ADPCM；不随源码或测试目录分发 FFmpeg。

- **Bingus Shared Loader**：运行时前置，通过其 API 1 加载插件和写入日志；不随本源码仓库分发。
- **Mod Options Menu**：可选设置界面前置；本项目调用其公开注册、读取及设置接口，不包含其实现或 Vanilla Plus 资源。
- **HD2Runtime**：任务状态字段的研究参考。v0.2.9 使用本项目内的只读检测和状态逻辑，不依赖或打包完整 HD2Runtime。参考：https://github.com/SkyeShade/HD2Runtime
- **游戏程序和 Lua VM**：原生字段与指令校验依赖对应游戏版本。游戏 DLL、解包内存和 `lua51.dll` 不随仓库分发；离线测试只加载开发者自行安装的 Lua DLL。
- **Rainie Love / 雨爱 DJ 音频**：歌曲权利归各自权利人。本源码仓库不包含 MP3 或内嵌歌曲的发布 ZIP；构建时需自行提供原始音频或本地已有安装包。

未在本次整理中为项目新增开源许可证；公开源代码不等于授予第三方素材的再分发权。
