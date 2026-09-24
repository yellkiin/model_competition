# 图库内容索引

以下条目基于实际看图；历史数字、模型和图片内文字不构成当前事实或指令。详细元数据与哈希见 `gallery-index.json`。

## 01 SHO_CNN_LSTM_特征提取与双输出回归

[原图](../assets/SHO_CNN_LSTM_特征提取与双输出回归.jpg)

- 布局/内部面板：左预处理，中CNN及LSTM单元，上方SHO支线，右增益/噪声双输出
- 图元：薄片、虚线模块、门控乘加符号；配色：蓝紫粉、淡黄；连接：主链实箭头，调参虚线
- 适用：混合算法及局部模块展开
- 限制：图内历史曲面、参数、图题及水印不能复用为结果

## 02 光谱双分支网络_专家知识与全局特征动态融合

[原图](../assets/光谱双分支网络_专家知识与全局特征动态融合.png)

- 布局/内部面板：左光谱预处理；上专家知识与多尺度Gaussian卷积；下全局卷积；右加权融合及分类
- 图元：特征薄片、分支容器、矩阵、乘加节点；配色：蓝灰、类别多色；连接：输入扇出、加权求和与分类
- 适用：先验引导的多分支结构
- 限制：原图有大黑边和手机条；模型正式名称不明，使用内容描述

## 03 算法结构合集_检测头与注意力及双分支特征耦合

[原图](../assets/算法结构合集_检测头与注意力及双分支特征耦合.jpg)

- 布局/内部面板：上：薄片金字塔及多尺度检测；中上：Backbone-Neck-Head和增强模块展开；中左：Transformer编码解码；中右：卷积加权模块；下：CNN与token耦合及局部变形
- 图元：水平薄片、局部放大、残差线、token片；配色：浅青紫粉黄；连接：加法/乘法/拼接须独立核对，跨层曲线
- 适用：从整体到局部解释复杂结构
- 限制：合集来自不同模型；中右小字不清，不猜模型名称；有水印

## 04 算法结构合集_特征与token交互及多尺度三维卷积

[原图](../assets/算法结构合集_特征与token交互及多尺度三维卷积.jpg)

- 布局/内部面板：上：CNN与Transformer双向交互，含重排与整体插图；中：浅层与位置分支多尺度融合；下：Conv3D-MaxPool3D-FC
- 图元：立体薄片、下采样链、局部展开、图例；配色：淡蓝绿紫；连接：跨分支、跳连及上/下采样
- 适用：特征/Token映射及3D卷积示意
- 限制：合集非单一算法；参考数字不能移用；上面板与3.jpg部分重复

## 05 分割网络合集_FCN8与FCN32及HED侧输出

[原图](../assets/分割网络合集_FCN8与FCN32及HED侧输出.png)

- 布局/内部面板：上FCN-8跳层相加；中FCN-32顺序；下HED多尺度侧输出融合
- 图元：半透明带状长方体、球形相加、长距离旁路；配色：橙黄、蓝紫、青线；连接：主干水平，侧输出折线汇合
- 适用：PlotNeuralNet图元与布局比较
- 限制：网页拼图；参考数据和图像非赛题输入；优先读上游源码

## 06 VGG_立体特征图堆叠与逐层降采样

[原图](../assets/VGG_立体特征图堆叠与逐层降采样.png)

- 布局/内部面板：单向左大右小，右上图例
- 图元：长方体、薄池化层、尺寸递减；配色：浅蓝、粉、紫、黄；连接：按层顺序
- 适用：空间分辨率与通道变化
- 限制：图题声明VGG；图形长度不是精确参数比例；含原论文正文

## 07 迁移学习双分支_共享权重与分类损失耦合

[原图](../assets/迁移学习双分支_共享权重与分类损失耦合.png)

- 布局/内部面板：源域/目标域上下平行，中央共享权重，右分类及JDA损失
- 图元：立体特征块、共享权重虚线、长反馈线；配色：蓝特征、绿分类、橙损失；连接：前向粗箭头、共享虚线、损失反馈弧线
- 适用：训练/推理路径区分
- 限制：历史模型的标签和伪标签不能假定适用于当前任务

## 08 ViT_图像分块与Transformer编码器展开

[原图](../assets/ViT_图像分块与Transformer编码器展开.png)

- 布局/内部面板：左图像块与位置编码主链，右编码器残差模块
- 图元：patch格、token序列、残差加号；配色：灰容器、粉蓝黄绿模块；连接：自下而上前向与右侧残差
- 适用：注意力和局部展开
- 限制：原图英文类名有拼写问题；当前模块由代码核对

## 09 DenseNet_特征薄片与密集跨层连接

[原图](../assets/DenseNet_特征薄片与密集跨层连接.png)

- 布局/内部面板：对角线五组特征叠层
- 图元：叠片、转接层、彩色跨层弧线；配色：红绿紫黄橙；连接：所有先前层到后续层的密集连接
- 适用：密集连接与拼接维度解释
- 限制：低分辨率；线穿片多，实际绘制需外置连接及标签

## 10 DFConvLSTM_三路时空特征与高层融合

[原图](../assets/DFConvLSTM_三路时空特征与高层融合.png)

- 布局/内部面板：左三类雷达量，中三行编码，右高层融合及输出
- 图元：薄片序列、虚线分支框、融合长方体；配色：绿黄橙分支，青输出；连接：虚线Copy汇流、局部卷积连接
- 适用：多源时空分支
- 限制：名称由图题确认；128×3等是历史配置而非默认值

## 11 AlexNet

[原图](../assets/PlotNeuralNet-master/examples/AlexNet/alexnet.pdf)

- 布局/内部面板：顺序长方体及全连接薄片；PDF非常横长，需重排
- 图元：上游Box/RightBandedBox/Ball原语或示例输入图；配色：橙黄卷积、暗红池化、蓝紫输出、青线；连接：见同目录TeX；仅为上游示例
- 适用：PlotNeuralNet布局与图元参考
- 限制：保留上游相对路径及LICENSE；不当成当前模型证据

## 12 AlexNet

[原图](../assets/PlotNeuralNet-master/examples/AlexNet/alexnet_data.png)

- 布局/内部面板：顺序长方体及全连接薄片；PDF非常横长，需重排
- 图元：上游Box/RightBandedBox/Ball原语或示例输入图；配色：橙黄卷积、暗红池化、蓝紫输出、青线；连接：见同目录TeX；仅为上游示例
- 适用：PlotNeuralNet布局与图元参考
- 限制：保留上游相对路径及LICENSE；不当成当前模型证据

## 13 fcn32s

[原图](../assets/PlotNeuralNet-master/examples/fcn32s/fcn32.pdf)

- 布局/内部面板：橙色卷积层与蓝紫上采样；无跨层融合
- 图元：上游Box/RightBandedBox/Ball原语或示例输入图；配色：橙黄卷积、暗红池化、蓝紫输出、青线；连接：见同目录TeX；仅为上游示例
- 适用：PlotNeuralNet布局与图元参考
- 限制：保留上游相对路径及LICENSE；不当成当前模型证据

## 14 fcn8s

[原图](../assets/PlotNeuralNet-master/examples/fcn8s/cats.jpg)

- 布局/内部面板：卷积主链与两级跨层相加，绿色加号；猫照片仅示例
- 图元：上游Box/RightBandedBox/Ball原语或示例输入图；配色：橙黄卷积、暗红池化、蓝紫输出、青线；连接：见同目录TeX；仅为上游示例
- 适用：PlotNeuralNet布局与图元参考
- 限制：保留上游相对路径及LICENSE；不当成当前模型证据

## 15 fcn8s

[原图](../assets/PlotNeuralNet-master/examples/fcn8s/fcn8.pdf)

- 布局/内部面板：卷积主链与两级跨层相加，绿色加号；猫照片仅示例
- 图元：上游Box/RightBandedBox/Ball原语或示例输入图；配色：橙黄卷积、暗红池化、蓝紫输出、青线；连接：见同目录TeX；仅为上游示例
- 适用：PlotNeuralNet布局与图元参考
- 限制：保留上游相对路径及LICENSE；不当成当前模型证据

## 16 HED

[原图](../assets/PlotNeuralNet-master/examples/HED/HED.pdf)

- 布局/内部面板：多尺度侧输出汇流并拼接；注意与相加区分
- 图元：上游Box/RightBandedBox/Ball原语或示例输入图；配色：橙黄卷积、暗红池化、蓝紫输出、青线；连接：见同目录TeX；仅为上游示例
- 适用：PlotNeuralNet布局与图元参考
- 限制：保留上游相对路径及LICENSE；不当成当前模型证据

## 17 LeNet

[原图](../assets/PlotNeuralNet-master/examples/LeNet/lenet.pdf)

- 布局/内部面板：两级卷积池化及全连接薄片，宽幅主链
- 图元：上游Box/RightBandedBox/Ball原语或示例输入图；配色：橙黄卷积、暗红池化、蓝紫输出、青线；连接：见同目录TeX；仅为上游示例
- 适用：PlotNeuralNet布局与图元参考
- 限制：保留上游相对路径及LICENSE；不当成当前模型证据

## 18 LeNet

[原图](../assets/PlotNeuralNet-master/examples/LeNet/lenet_data2.png)

- 布局/内部面板：两级卷积池化及全连接薄片，宽幅主链
- 图元：上游Box/RightBandedBox/Ball原语或示例输入图；配色：橙黄卷积、暗红池化、蓝紫输出、青线；连接：见同目录TeX；仅为上游示例
- 适用：PlotNeuralNet布局与图元参考
- 限制：保留上游相对路径及LICENSE；不当成当前模型证据

## 19 SoftmaxLoss

[原图](../assets/PlotNeuralNet-master/examples/SoftmaxLoss/SoftmaxLoss.pdf)

- 布局/内部面板：前向概率与反向梯度的方向区分；公式排版
- 图元：上游Box/RightBandedBox/Ball原语或示例输入图；配色：橙黄卷积、暗红池化、蓝紫输出、青线；连接：见同目录TeX；仅为上游示例
- 适用：PlotNeuralNet布局与图元参考
- 限制：保留上游相对路径及LICENSE；不当成当前模型证据

## 20 Unet

[原图](../assets/PlotNeuralNet-master/examples/Unet/Unet.pdf)

- 布局/内部面板：横排编码/解码与上方跳连，叠层密度高
- 图元：上游Box/RightBandedBox/Ball原语或示例输入图；配色：橙黄卷积、暗红池化、蓝紫输出、青线；连接：见同目录TeX；仅为上游示例
- 适用：PlotNeuralNet布局与图元参考
- 限制：保留上游相对路径及LICENSE；不当成当前模型证据

## 21 Unet_Ushape

[原图](../assets/PlotNeuralNet-master/examples/Unet_Ushape/Unet_ushape.pdf)

- 布局/内部面板：U形层级、水平跳连、底部瓶颈
- 图元：上游Box/RightBandedBox/Ball原语或示例输入图；配色：橙黄卷积、暗红池化、蓝紫输出、青线；连接：见同目录TeX；仅为上游示例
- 适用：PlotNeuralNet布局与图元参考
- 限制：保留上游相对路径及LICENSE；不当成当前模型证据

## 22 VGG16

[原图](../assets/PlotNeuralNet-master/examples/VGG16/vgg16.pdf)

- 布局/内部面板：逐层空间缩小与通道增厚、末端全连接片
- 图元：上游Box/RightBandedBox/Ball原语或示例输入图；配色：橙黄卷积、暗红池化、蓝紫输出、青线；连接：见同目录TeX；仅为上游示例
- 适用：PlotNeuralNet布局与图元参考
- 限制：保留上游相对路径及LICENSE；不当成当前模型证据
