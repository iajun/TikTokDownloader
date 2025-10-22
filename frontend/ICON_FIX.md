# 图标使用修复说明

## 问题描述

在 Vue 3 中使用 Ant Design Vue 图标时，遇到错误：
```
Cannot read properties of undefined (reading 'attrs')
```

## 解决方案

### 正确导入方式

```typescript
import { h } from 'vue'
import { HomeOutlined } from '@ant-design/icons-vue'
```

### 在模板中使用

有两种方式：

#### 方式1: 使用 component :is

```vue
<template #icon>
  <component :is="h(HomeOutlined)" />
</template>
```

#### 方式2: 在 menuItems 中使用函数

```typescript
const menuItems = [
  {
    key: 'home',
    label: '首页',
    icon: () => h(HomeOutlined),  // 返回渲染函数
  },
]
```

## 修复的文件

1. `src/views/Home.vue` - 首页图标
2. `src/views/Tasks.vue` - 任务管理图标
3. `src/views/History.vue` - 历史记录图标
4. `src/layouts/DefaultLayout.vue` - 导航菜单图标

## 正确的导入模式

### 在 <script setup> 中

```typescript
<script setup lang="ts">
import { ref, h } from 'vue'  // 导入 h
import { HomeOutlined } from '@ant-design/icons-vue'
</script>
```

### 使用图标组件

```vue
<template>
  <!-- 在按钮中 -->
  <a-button>
    <template #icon>
      <component :is="h(HomeOutlined)" />
    </template>
    按钮文字
  </a-button>
  
  <!-- 在菜单中 -->
  <a-menu :items="menuItems" />
</template>
```

## 示例代码

### 完整的组件示例

```vue
<template>
  <div>
    <a-button type="primary">
      <template #icon>
        <component :is="iconRenderer" />
      </template>
      开始处理
    </a-button>
  </div>
</template>

<script setup lang="ts">
import { h } from 'vue'
import { PlayCircleOutlined } from '@ant-design/icons-vue'

const iconRenderer = () => h(PlayCircleOutlined)
</script>
```

## 注意事项

1. ✅ 必须导入 `h` 函数
2. ✅ 图标必须作为函数返回
3. ✅ 使用 `component :is` 渲染组件
4. ❌ 不能直接使用 `<HomeOutlined />`

## 参考文档

- [Ant Design Vue 图标](https://antdv.com/components/icon-cn)
- [Vue 3 h() 函数](https://cn.vuejs.org/api/render-function.html)

## 效果

修复后，所有图标都能正常显示：
- ✅ 首页图标
- ✅ 任务管理图标  
- ✅ 历史记录图标
- ✅ 刷新按钮图标
