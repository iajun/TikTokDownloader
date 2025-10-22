<template>
  <a-layout style="min-height: 100vh">
    <!-- Top Header Bar -->
    <a-layout-header class="top-header">
      <div class="header-left">
        <menu-unfold-outlined v-if="collapsed" class="trigger" @click="toggleCollapsed" />
        <menu-fold-outlined v-else class="trigger" @click="toggleCollapsed" />
        <div class="logo">
          <span class="logo-icon">🎬</span>
          <span class="logo-text">AI视频总结</span>
        </div>
      </div>
      <div class="header-right">
        <a-space>
          <span>{{ userName }}</span>
          <a-avatar>{{ userName?.[0] || 'U' }}</a-avatar>
          <global-outlined />
        </a-space>
      </div>
    </a-layout-header>

    <a-layout class="main-layout">
      <!-- Left Sidebar -->
      <a-layout-sider 
        v-model:collapsed="collapsed" 
        :trigger="null" 
        collapsible
        class="sidebar"
        :width="200"
      >
        <div class="logo-collapsed" v-if="collapsed">
          <span class="logo-icon">🎬</span>
        </div>
        <a-menu
          v-model:selectedKeys="selectedKeys"
          mode="inline"
          theme="dark"
          :items="menuItems"
          @click="handleMenuClick"
        />
      </a-layout-sider>

      <!-- Main Content -->
      <a-layout-content class="main-content">
        <!-- Breadcrumbs -->
        <a-breadcrumb class="breadcrumb">
          <a-breadcrumb-item>Home</a-breadcrumb-item>
          <a-breadcrumb-item>{{ pageTitle }}</a-breadcrumb-item>
        </a-breadcrumb>
        
        <!-- Content Wrapper -->
        <div class="content-wrapper">
          <router-view />
        </div>
      </a-layout-content>
    </a-layout>
  </a-layout>
</template>

<script setup lang="ts">
import { ref, computed, watch, h } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { 
  HomeOutlined, 
  UnorderedListOutlined, 
  FileTextOutlined, 
  SettingOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  GlobalOutlined,
  StarOutlined
} from '@ant-design/icons-vue'

const router = useRouter()
const route = useRoute()
const selectedKeys = ref<string[]>([])
const collapsed = ref<boolean>(false)
const userName = ref<string>('用户') // You can replace this with actual user data

const menuItems = [
  {
    key: 'home',
    label: '首页',
    icon: () => h(HomeOutlined),
  },
  {
    key: 'tasks',
    label: '任务管理',
    icon: () => h(UnorderedListOutlined),
  },
      {
        key: 'history',
        label: '历史记录',
        icon: () => h(FileTextOutlined),
      },
      {
        key: 'favorites',
        label: '收藏夹',
        icon: () => h(StarOutlined),
      },
      {
        key: 'settings',
        label: '设置',
        icon: () => h(SettingOutlined),
      },
]

const pageTitle = computed(() => {
  const path = route.path
  if (path === '/') {
    return '首页'
  } else if (path.startsWith('/tasks')) {
    return '任务管理'
  } else if (path.startsWith('/history')) {
    return '历史记录'
  } else if (path.startsWith('/favorites')) {
    return '收藏夹'
  } else if (path.startsWith('/detail')) {
    return '视频详情'
  } else if (path.startsWith('/settings')) {
    return '系统设置'
  }
  return 'AI视频总结工具'
})

// 根据当前路由设置选中的菜单项
watch(
  () => route.path,
  (path) => {
    if (path === '/') {
      selectedKeys.value = ['home']
    } else if (path.startsWith('/tasks')) {
      selectedKeys.value = ['tasks']
    } else if (path.startsWith('/history')) {
      selectedKeys.value = ['history']
    } else if (path.startsWith('/favorites')) {
      selectedKeys.value = ['favorites']
    } else if (path.startsWith('/detail')) {
      selectedKeys.value = []
    } else if (path.startsWith('/settings')) {
      selectedKeys.value = ['settings']
    }
  },
  { immediate: true }
)

const handleMenuClick = ({ key }: { key: string }) => {
  switch (key) {
    case 'home':
      router.push('/')
      break
    case 'tasks':
      router.push('/tasks')
      break
    case 'history':
      router.push('/history')
      break
    case 'settings':
      router.push('/settings')
      break
    case 'favorites':
      router.push('/favorites')
      break
  }
}

const toggleCollapsed = () => {
  collapsed.value = !collapsed.value
}
</script>

<style scoped>
/* Top Header */
.top-header {
  background: #fff;
  padding: 0 24px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  border-bottom: 1px solid #f0f0f0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 64px;
  line-height: 64px;
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 100;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.trigger {
  font-size: 18px;
  cursor: pointer;
  padding: 0 24px;
  transition: color 0.3s;
}

.trigger:hover {
  color: #1890ff;
}

.logo {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 16px;
  font-weight: 600;
}

.logo-icon {
  font-size: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
}

.logo-text {
  color: #1890ff;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

/* Main Layout */
.main-layout {
  position: fixed;
  top: 64px;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
}

/* Sidebar */
.sidebar {
  overflow: auto;
  background: #001529;
}

.logo-collapsed {
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #002140;
  border-bottom: 1px solid #001529;
}

.logo-collapsed .logo-icon {
  font-size: 24px;
}

/* Main Content */
.main-content {
  flex: 1;
  background: #f0f2f5;
  padding: 0;
  overflow: auto;
  transition: all 0.2s;
}

.breadcrumb {
  background: #f0f2f5;
  padding: 16px 24px;
  margin-bottom: 0;
}

.content-wrapper {
  padding: 24px;
}

/* Menu Styles */
:deep(.sidebar .ant-menu) {
  border-right: none;
}

:deep(.sidebar .ant-menu-item) {
  margin: 4px 0;
  border-radius: 4px;
}

/* Handle sidebar collapse */
:deep(.sidebar.ant-layout-sider-collapsed) {
  width: 80px !important;
  min-width: 80px !important;
  max-width: 80px !important;
}

/* Responsive */
@media (max-width: 768px) {
  .top-header {
    padding: 0 16px;
  }

  .content-wrapper {
    padding: 16px;
  }
}
</style>
