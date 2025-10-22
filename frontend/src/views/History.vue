<template>
  <a-card>
    <template #title>
      <div class="header">
        <span>📚 历史记录</span>
        <a-button @click="refreshRecords" :loading="loading">
          <template #icon>
            <component :is="h(ReloadOutlined)" />
          </template>
          刷新
        </a-button>
      </div>
    </template>
    
    <a-table
      :columns="columns"
      :data-source="records"
      :pagination="{ pageSize: 10 }"
      :loading="loading"
      row-key="id"
      @change="handleTableChange"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'url'">
          <a :href="record.url" target="_blank" style="max-width: 300px; display: block">
            {{ record.url }}
          </a>
        </template>
        
        <template v-if="column.key === 'created_at'">
          <span>{{ formatDate(record.created_at) }}</span>
        </template>
        
        <template v-if="column.key === 'summary'">
          <div style="max-width: 400px; overflow: hidden; text-overflow: ellipsis">
            {{ record.summary || '暂无总结' }}
          </div>
        </template>
        
        <template v-if="column.key === 'actions'">
          <a-space>
            <a-button type="link" size="small" @click="viewDetail(record)">
              查看详情
            </a-button>
            <a-button
              v-if="false"
              type="link"
              size="small"
              disabled
            >
              重新总结
            </a-button>
          </a-space>
        </template>
      </template>
    </a-table>
  </a-card>
</template>

<script setup lang="ts">
import { ref, onMounted, h } from 'vue'
import { message } from 'ant-design-vue'
import { ReloadOutlined } from '@ant-design/icons-vue'
import { getAllRecords } from '@/api/task'
import type { Record } from '@/api/task'
import { useRouter } from 'vue-router'

const router = useRouter()

const loading = ref(false)
const records = ref<Record[]>([])

const formatDate = (dateStr: string) => {
  const date = new Date(dateStr)
  return date.toLocaleString('zh-CN')
}

const refreshRecords = async () => {
  loading.value = true
  try {
    const response = await getAllRecords()
    if (response.success) {
      records.value = response.data
    }
  } catch (error: any) {
    message.error(error.message || '加载失败')
  } finally {
    loading.value = false
  }
}

const viewDetail = (record: Record) => {
  router.push(`/detail/${record.id}`)
}

const handleTableChange = (pagination: any) => {
  // 处理分页变化
  console.log('pagination:', pagination)
}

onMounted(() => {
  refreshRecords()
})

const columns = [
  {
    title: '链接',
    key: 'url',
    dataIndex: 'url',
    ellipsis: true,
  },
  {
    title: '创建时间',
    key: 'created_at',
    dataIndex: 'created_at',
    width: 180,
  },
  {
    title: '总结',
    key: 'summary',
    dataIndex: 'summary',
    ellipsis: true,
  },
  {
    title: '操作',
    key: 'actions',
    width: 200,
  },
]
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

:deep(.ant-table) {
  border-radius: 8px;
  overflow: hidden;
}
</style>
