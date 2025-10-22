<template>
  <a-card>
    <template #title>
      <div class="header">
        <span>📋 任务管理</span>
        <a-button @click="refreshTasks" :loading="loading">
          <template #icon>
            <component :is="h(ReloadOutlined)" />
          </template>
          刷新
        </a-button>
      </div>
    </template>
    
    <a-tabs v-model:activeKey="activeTab" @change="handleTabChange">
      <a-tab-pane key="all" tab="全部">
        <TaskList 
          :tasks="allTasks" 
          :pagination="paginationConfig"
          :total="totalTasks"
          @change="handleTableChange"
          @refresh="refreshTasks"
        />
      </a-tab-pane>
      <a-tab-pane key="running" tab="进行中">
        <TaskList 
          :tasks="displayRunningTasks" 
          :pagination="getRunningPaginationConfig"
          :total="runningTasks.length"
          @change="handleRunningTableChange"
          @refresh="refreshTasks"
        />
      </a-tab-pane>
      <a-tab-pane key="completed" tab="已完成">
        <TaskList 
          :tasks="completedTasks" 
          :pagination="paginationConfig"
          :total="totalTasks"
          @change="handleTableChange"
          @refresh="refreshTasks"
        />
      </a-tab-pane>
      <a-tab-pane key="failed" tab="失败">
        <TaskList 
          :tasks="failedTasks" 
          :pagination="paginationConfig"
          :total="totalTasks"
          @change="handleTableChange"
          @refresh="refreshTasks"
        />
      </a-tab-pane>
    </a-tabs>
  </a-card>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, h } from 'vue'
import { ReloadOutlined } from '@ant-design/icons-vue'
import { getAllTasks } from '@/api/task'
import type { TaskStatus } from '@/api/task'
import TaskList from '@/components/TaskList.vue'

const loading = ref(false)
const activeTab = ref('all')
const refreshInterval = ref<ReturnType<typeof setInterval>>()

// 分页相关
const currentPage = ref(1)
const pageSize = ref(20)
const totalTasks = ref(0)

const paginationConfig = computed(() => ({
  current: currentPage.value,
  pageSize: pageSize.value,
  total: totalTasks.value,
  showSizeChanger: true,
  showQuickJumper: true,
  showTotal: (total: number) => `共 ${total} 条`,
  pageSizeOptions: ['10', '20', '50', '100']
}))

// 进行中任务的分页配置（客户端分页）
const getRunningPaginationConfig = computed(() => {
  if (activeTab.value !== 'running') {
    return false
  }
  return {
    current: currentPage.value,
    pageSize: pageSize.value,
    total: runningTasks.value.length,
    showSizeChanger: true,
    showQuickJumper: true,
    showTotal: (total: number) => `共 ${total} 条`,
    pageSizeOptions: ['10', '20', '50', '100']
  }
})

const allTasks = ref<TaskStatus[]>([])
const runningTasks = ref<TaskStatus[]>([])
const completedTasks = ref<TaskStatus[]>([])
const failedTasks = ref<TaskStatus[]>([])

// 获取当前显示的任务列表（用于进行中标签页的客户端分页）
const displayRunningTasks = computed(() => {
  if (activeTab.value !== 'running') {
    return []
  }
  const start = (currentPage.value - 1) * pageSize.value
  const end = start + pageSize.value
  return runningTasks.value.slice(start, end)
})

// 获取当前标签页对应的状态筛选（注意：后端API只支持单个状态筛选）
// 对于"进行中"状态，我们需要获取多个状态，但后端只支持单个状态
// 这里我们先获取所有任务，然后在客户端筛选
const getStatusFilter = () => {
  switch (activeTab.value) {
    case 'running':
      // 注意：后端只支持单个状态筛选，所以我们需要在客户端筛选
      // 或者可以多次请求，这里先返回undefined，在客户端筛选
      return undefined
    case 'completed':
      return 'completed'
    case 'failed':
      return 'failed'
    default:
      return undefined
  }
}

const refreshTasks = async () => {
  loading.value = true
  try {
    const status = getStatusFilter()
    const response = await getAllTasks(pageSize.value, (currentPage.value - 1) * pageSize.value, status)
    if (response.success) {
      totalTasks.value = response.total
      
      // 根据状态分类任务
      if (status) {
        // 如果指定了状态，直接使用返回的数据
        const tasks = response.data
        if (status === 'completed') {
          completedTasks.value = tasks
        } else if (status === 'failed') {
          failedTasks.value = tasks
        }
        // 对于其他状态，也需要更新allTasks以保持一致性
        allTasks.value = response.data
      } else {
        // 如果没有指定状态（全部或进行中），需要获取所有任务并进行筛选
      // 注意：为了正确统计"进行中"任务的数量，我们需要获取所有任务
      // 但这里我们只获取当前页的数据，所以"进行中"的统计可能不准确
      // 如果需要准确的"进行中"任务数量，需要单独请求所有进行中状态的任务
      allTasks.value = response.data
      // 筛选进行中的任务（从当前页数据中筛选）
      runningTasks.value = response.data.filter(t => 
        ['pending', 'downloading', 'extracting_audio', 'transcribing', 'summarizing'].includes(t.status)
      )
        completedTasks.value = response.data.filter(t => t.status === 'completed')
        failedTasks.value = response.data.filter(t => t.status === 'failed')
      }
      
      // 如果是"进行中"标签页，我们需要获取所有任务来正确统计和分页
      if (activeTab.value === 'running') {
        // 获取所有任务用于筛选进行中的任务（获取足够多的数据）
        const allResponse = await getAllTasks(1000, 0)
        if (allResponse.success) {
          runningTasks.value = allResponse.data.filter(t => 
            ['pending', 'downloading', 'extracting_audio', 'transcribing', 'summarizing'].includes(t.status)
          )
        }
      }
    }
  } finally {
    loading.value = false
  }
}

const handleTabChange = () => {
  // 切换标签页时重置到第一页并刷新
  currentPage.value = 1
  refreshTasks()
}

// 处理列表分页变化
const handleTableChange = (pagination: any) => {
  // TaskList 发出的是 { page, pageSize }，需要适配
  currentPage.value = pagination.page ?? pagination.current
  pageSize.value = pagination.pageSize
  refreshTasks()
}

// 处理进行中任务的分页变化（客户端分页）
const handleRunningTableChange = (pagination: any) => {
  // TaskList 发出的是 { page, pageSize }，需要适配
  currentPage.value = pagination.page ?? pagination.current
  pageSize.value = pagination.pageSize
  // 对于客户端分页，不需要重新请求，只需要更新页码即可
}

onMounted(() => {
  refreshTasks()
  // 每5秒自动刷新一次
  refreshInterval.value = setInterval(refreshTasks, 5000)
})

onUnmounted(() => {
  if (refreshInterval.value) {
    clearInterval(refreshInterval.value)
  }
})
</script>

<style scoped>
.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

:deep(.ant-card) {
  border-radius: 16px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.6);
  backdrop-filter: blur(10px);
  background: rgba(255, 255, 255, 0.98);
  transition: all 0.3s ease;
}

:deep(.ant-card:hover) {
  box-shadow: 0 12px 48px rgba(0, 0, 0, 0.12);
  transform: translateY(-2px);
}

:deep(.ant-card-head) {
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
  padding: 20px 24px;
}

:deep(.ant-card-body) {
  padding: 24px;
}

:deep(.ant-tabs-tab) {
  padding: 12px 24px;
}
</style>
