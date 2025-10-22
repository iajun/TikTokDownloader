<template>
  <div>
    <div v-if="selectedRowKeys.length > 0" class="batch-actions">
      <a-space>
        <span>已选择 {{ selectedRowKeys.length }} 项</span>
        <a-button 
          v-if="!props.folderId"
          type="primary"
          @click="showAddToCollectionModal"
          :icon="h(StarOutlined)"
        >
          添加到收藏夹
        </a-button>
        <a-button
          v-if="props.showRemoveFromFolder && props.folderId"
          danger
          @click="batchRemoveFromFolder"
          :loading="batchDeleteLoading"
        >
          从收藏夹移除
        </a-button>
        <a-button danger @click="batchDelete" :loading="batchDeleteLoading">
          批量删除
        </a-button>
        <a-button @click="clearSelection">取消选择</a-button>
      </a-space>
    </div>
    <a-table
      :columns="columns"
      :data-source="tasks"
      :pagination="paginationConfig"
      :loading="loading"
      :row-selection="rowSelection"
      row-key="id"
      @change="handleTableChange"
    >
    <template #bodyCell="{ column, record }">
      <template v-if="column.key === 'cover'">
        <div class="cover-container">
          <img
            v-if="record.video?.static_cover || record.video?.dynamic_cover"
            :src="record.video?.static_cover || record.video?.dynamic_cover"
            class="cover-image"
            alt="视频封面"
          />
          <div v-if="!record.video?.static_cover && !record.video?.dynamic_cover" class="no-cover">
            <span>📹</span>
          </div>
        </div>
      </template>
      
      <template v-if="column.key === 'tags'">
        <div v-if="record.video?.tag && parseTags(record.video.tag).length > 0" class="tags-container">
          <a-tag 
            v-for="(tag, index) in parseTags(record.video.tag)" 
            :key="index" 
            color="blue" 
            size="small"
            class="tag-item"
          >
            {{ tag }}
          </a-tag>
        </div>
        <div v-else class="no-tags">无标签</div>
      </template>
      
      <template v-if="column.key === 'id'">
        <span class="task-id-cell">{{ record.id }}</span>
      </template>
      
      <template v-if="column.key === 'desc'">
        <div class="video-info">
          <div class="video-platform-tag" v-if="record.platform">
            <a-tag :color="record.platform === 'douyin' ? 'red' : 'blue'" size="small">
              {{ record.platform === 'douyin' ? '抖音' : 'TikTok' }}
            </a-tag>
          </div>
          <div v-if="record.video?.desc" class="video-desc">{{ record.video.desc }}</div>
          <div v-else class="video-desc-empty">无描述</div>
          <div v-if="record.video?.nickname" class="video-author">
            <span class="author-label">作者：</span>{{ record.video.nickname }}
            <span v-if="record.video?.unique_id" class="author-id"> (@{{ record.video.unique_id }})</span>
          </div>
        </div>
      </template>
      
      <template v-if="column.key === 'url'">
        <a :href="record.url" target="_blank" style="max-width: 200px; overflow: hidden; text-overflow: ellipsis; display: block">
          {{ record.url }}
        </a>
      </template>
      
      <template v-if="column.key === 'status'">
        <a-tag :color="getStatusColor(record.status)">
          {{ getStatusText(record.status) }}
        </a-tag>
      </template>
      
      <template v-if="column.key === 'progress'">
        <a-progress :percent="record.progress" :status="record.status === 'failed' ? 'exception' : undefined" />
      </template>
      
      <template v-if="column.key === 'message'">
        <span>{{ record.message }}</span>
      </template>
      
      <template v-if="column.key === 'actions'">
        <a-space>
          <a-button type="link" size="small" @click="viewTask(record)">查看</a-button>
          <a-button
            v-if="record.status !== 'completed'"
            type="link"
            size="small"
            @click="retryTask(record)"
            :loading="retryLoadingMap[record.id]"
          >
            重试
          </a-button>
          <a-button
            v-if="props.showRemoveFromFolder && props.folderId"
            type="link"
            size="small"
            danger
            @click="removeFromFolder(record)"
          >
            从收藏夹移除
          </a-button>
          <a-button
            v-if="record.status === 'completed' || record.status === 'failed'"
            type="link"
            size="small"
            danger
            @click="deleteTask(record)"
          >
            删除
          </a-button>
        </a-space>
      </template>
    </template>
    </a-table>
    
    <!-- 添加到收藏夹对话框 -->
    <a-modal
      v-model:open="addToCollectionModalVisible"
      title="添加到收藏夹"
      :confirm-loading="addToCollectionLoading"
      @ok="handleAddToCollectionOk"
      @cancel="() => { addToCollectionModalVisible = false; selectedFolderId = null }"
      width="500px"
    >
      <div style="padding: 16px 0;">
        <p style="margin-bottom: 16px;">
          选择要将 {{ selectedRowKeys.length }} 个任务添加到的收藏夹：
        </p>
        <a-tree-select
          v-model:value="selectedFolderId"
          :tree-data="collectionTreeData"
          placeholder="请选择收藏夹"
          :tree-default-expand-all="true"
          style="width: 100%"
          :allow-clear="true"
        />
      </div>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, h, computed } from 'vue'
import { message, Modal } from 'ant-design-vue'
import type { TaskStatus } from '@/api/task'
import { useRouter } from 'vue-router'
import { ExclamationCircleOutlined } from '@ant-design/icons-vue'
import { retryTask as retryTaskApi, batchDeleteTasks } from '@/api/task'
import { addTasksToCollection, removeTaskFromCollection, batchRemoveTasksFromCollection, getCollectionTree } from '@/api/collection'
import { StarOutlined } from '@ant-design/icons-vue'

const router = useRouter()
const loading = ref(false)
const retryLoadingMap = ref<{ [key: number]: boolean }>({})
const selectedRowKeys = ref<number[]>([])
const batchDeleteLoading = ref(false)

// 添加到收藏夹相关状态
const addToCollectionModalVisible = ref(false)
const collectionTreeData = ref<any[]>([])
const selectedFolderId = ref<number | null>(null)
const addToCollectionLoading = ref(false)

interface Props {
  tasks: TaskStatus[]
  folderId?: number | null  // 收藏夹ID（当在收藏夹页面时）
  showRemoveFromFolder?: boolean  // 是否显示"从收藏夹移除"按钮
  simpleMode?: boolean  // 简化模式：只显示封面和视频信息
  pagination?: boolean | object  // 分页配置，false表示不分页
  total?: number  // 总数据量（用于分页）
}

const props = defineProps<Props>()

const emit = defineEmits<{
  refresh: []
  change: [pagination: any]
}>()

// 分页配置
const paginationConfig = computed(() => {
  if (props.pagination === false) {
    return false
  }
  
  if (typeof props.pagination === 'object') {
    return props.pagination
  }
  
  // 如果传入了pagination属性（即使为true），启用默认分页配置
  if (props.pagination === true || props.pagination !== undefined) {
    return {
      total: props.total || props.tasks.length,
      showSizeChanger: true,
      showQuickJumper: true,
      showTotal: (total: number) => `共 ${total} 条`,
      pageSizeOptions: ['10', '20', '50', '100']
    }
  }
  
  // 默认不启用分页
  return false
})

// 处理表格变化（分页、排序等）
const handleTableChange = (pagination: any) => {
  emit('change', pagination)
}

// 行选择配置：只能选择已完成或失败的任务
const rowSelection = computed(() => ({
  selectedRowKeys: selectedRowKeys.value,
  onChange: (keys: number[]) => {
    selectedRowKeys.value = keys
  },
  getCheckboxProps: (record: TaskStatus) => ({
    disabled: record.status !== 'completed' && record.status !== 'failed',
    name: record.id.toString(),
  }),
  hideSelectAll: false,
}))

const clearSelection = () => {
  selectedRowKeys.value = []
}

const getStatusColor = (status: string) => {
  const colors: { [key: string]: string } = {
    pending: 'default',
    downloading: 'processing',
    extracting_audio: 'processing',
    transcribing: 'processing',
    summarizing: 'processing',
    completed: 'success',
    failed: 'error',
  }
  return colors[status] || 'default'
}

const getStatusText = (status: string) => {
  const texts: { [key: string]: string } = {
    pending: '等待中',
    downloading: '下载中',
    extracting_audio: '提取音频',
    transcribing: '转录中',
    summarizing: 'AI总结中',
    completed: '已完成',
    failed: '失败',
  }
  return texts[status] || status
}

const parseTags = (tagString?: string): string[] => {
  if (!tagString) return []
  
  try {
    // 尝试解析JSON数组
    const parsed = JSON.parse(tagString)
    if (Array.isArray(parsed)) {
      return parsed
    }
  } catch {
    // 如果不是JSON，按逗号分割
    return tagString.split(',').map(t => t.trim()).filter(t => t)
  }
  
  return []
}

const viewTask = (task: TaskStatus) => {
  // 如果已完成，跳转到详情页
  if (task.status === 'completed') {
    router.push(`/detail/${task.id}`)
  } else {
    message.info(`任务状态: ${getStatusText(task.status)}, 进度: ${task.progress}%`)
  }
}

const cancelTask = (task: TaskStatus) => {
  Modal.confirm({
    title: '确认取消',
    icon: h(ExclamationCircleOutlined),
    content: '确定要取消这个任务吗？',
    async onOk() {
      try {
        // 注意：ai_service 不支持取消任务，这里先提示
        message.warning('后端暂不支持取消功能')
      } catch (error: any) {
        message.error(error.message || '操作失败')
      }
    },
  })
}

const retryTask = async (task: TaskStatus) => {
  retryLoadingMap.value[task.id] = true
  try {
    const response = await retryTaskApi(task.id)
    if (response.success) {
      message.success('任务已重新提交，将开始处理')
      // 刷新任务列表
      setTimeout(() => {
        location.reload()
      }, 1000)
    } else {
      message.error('重试失败')
    }
  } catch (error: any) {
    message.error(error.response?.data?.detail || error.message || '操作失败')
  } finally {
    retryLoadingMap.value[task.id] = false
  }
}

const deleteTask = (task: TaskStatus) => {
  const statusText = task.status === 'completed' ? '已完成' : task.status === 'failed' ? '失败' : ''
  
  Modal.confirm({
    title: '确认删除',
    icon: h(ExclamationCircleOutlined),
    content: `确定要删除这个${statusText}的任务吗？此操作不可恢复。`,
    okText: '删除',
    okType: 'danger',
    async onOk() {
      try {
        const { deleteTask: deleteTaskApi } = await import('@/api/task')
        await deleteTaskApi(task.id)
        message.success('任务已删除')
        location.reload()
      } catch (error: any) {
        message.error(error.response?.data?.detail || error.message || '删除失败')
      }
    },
  })
}

const batchDelete = () => {
  if (selectedRowKeys.value.length === 0) {
    message.warning('请选择要删除的任务')
    return
  }
  
  Modal.confirm({
    title: '确认批量删除',
    icon: h(ExclamationCircleOutlined),
    content: `确定要删除选中的 ${selectedRowKeys.value.length} 个任务吗？此操作不可恢复。`,
    okText: '删除',
    okType: 'danger',
    async onOk() {
      batchDeleteLoading.value = true
      try {
        const response = await batchDeleteTasks(selectedRowKeys.value)
        if (response.success) {
          message.success(`成功删除 ${response.data?.deleted_count || 0} 个任务`)
          selectedRowKeys.value = []
          location.reload()
        } else {
          message.error('批量删除失败')
        }
      } catch (error: any) {
        message.error(error.response?.data?.detail || error.message || '批量删除失败')
      } finally {
        batchDeleteLoading.value = false
      }
    },
  })
}

// 添加到收藏夹
const showAddToCollectionModal = async () => {
  if (selectedRowKeys.value.length === 0) {
    message.warning('请选择要添加到收藏夹的任务')
    return
  }
  
  try {
    const response = await getCollectionTree()
    if (!response.success || !response.data || response.data.length === 0) {
      message.warning('请先创建收藏夹')
      return
    }
    
    // 构建收藏夹选择器数据
    const buildSelectOptions = (folders: any[]): any[] => {
      return folders.map(folder => ({
        title: folder.name + (folder.task_count ? ` (${folder.task_count})` : ''),
        value: folder.id,
        key: folder.id,
        children: folder.children ? buildSelectOptions(folder.children) : []
      }))
    }
    
    collectionTreeData.value = buildSelectOptions(response.data)
    selectedFolderId.value = null
    addToCollectionModalVisible.value = true
  } catch (error: any) {
    message.error(error.response?.data?.detail || error.message || '加载收藏夹失败')
  }
}

const handleAddToCollectionOk = async () => {
  if (!selectedFolderId.value) {
    message.warning('请选择收藏夹')
    return
  }
  
  addToCollectionLoading.value = true
  try {
    const response = await addTasksToCollection(selectedFolderId.value, selectedRowKeys.value)
    if (response.success) {
      message.success(response.message || '添加成功')
      selectedRowKeys.value = []
      addToCollectionModalVisible.value = false
      selectedFolderId.value = null
    }
  } catch (error: any) {
    message.error(error.response?.data?.detail || error.message || '添加失败')
  } finally {
    addToCollectionLoading.value = false
  }
}

// 从收藏夹移除
const removeFromFolder = (task: TaskStatus) => {
  if (!props.folderId) return
  
  Modal.confirm({
    title: '确认移除',
    icon: h(ExclamationCircleOutlined),
    content: '确定要从收藏夹移除这个任务吗？',
    okText: '移除',
    okType: 'danger',
    async onOk() {
      try {
        await removeTaskFromCollection(props.folderId!, task.id)
        message.success('已从收藏夹移除')
        emit('refresh')
      } catch (error: any) {
        message.error(error.response?.data?.detail || error.message || '移除失败')
      }
    },
  })
}

const batchRemoveFromFolder = () => {
  if (!props.folderId || selectedRowKeys.value.length === 0) {
    message.warning('请选择要移除的任务')
    return
  }
  
  Modal.confirm({
    title: '确认批量移除',
    icon: h(ExclamationCircleOutlined),
    content: `确定要从收藏夹移除选中的 ${selectedRowKeys.value.length} 个任务吗？`,
    okText: '移除',
    okType: 'danger',
    async onOk() {
      batchDeleteLoading.value = true
      try {
        const response = await batchRemoveTasksFromCollection(props.folderId!, selectedRowKeys.value)
        if (response.success) {
          message.success(`成功移除 ${response.data?.deleted_count || 0} 个任务`)
          selectedRowKeys.value = []
          emit('refresh')
        }
      } catch (error: any) {
        message.error(error.response?.data?.detail || error.message || '移除失败')
      } finally {
        batchDeleteLoading.value = false
      }
    },
  })
}

// 根据模式决定显示的列
const columns = computed(() => {
  if (props.simpleMode) {
    // 简化模式：只显示封面和视频信息
    return [
      {
        title: '封面',
        key: 'cover',
        width: 150,
      },
      {
        title: '视频信息',
        key: 'desc',
        minWidth: 400,
      },
      {
        title: '操作',
        key: 'actions',
        width: 150,
        fixed: 'right',
      },
    ]
  }
  
  // 完整模式：显示所有列
  return [
    {
      title: 'ID',
      key: 'id',
      dataIndex: 'id',
      width: 80,
    },
    {
      title: '封面',
      key: 'cover',
      width: 110,
    },
    {
      title: '视频信息',
      key: 'desc',
      minWidth: 300,
    },
    {
      title: '标签',
      key: 'tags',
      minWidth: 200,
    },
    {
      title: '状态',
      key: 'status',
      dataIndex: 'status',
      width: 110,
    },
    {
      title: '进度',
      key: 'progress',
      dataIndex: 'progress',
      width: 180,
    },
    {
      title: '操作',
      key: 'actions',
      width: 180,
      fixed: 'right',
    },
  ]
})
</script>

<style scoped>
.cover-container {
  display: flex;
  justify-content: center;
  align-items: center;
  width: 90px;
  height: 120px;
}

.cover-image {
  width: 100%;
  height: 100%;
  object-fit: contain;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  cursor: pointer;
  transition: transform 0.2s;
  background: #f5f5f5;
}

.cover-image:hover {
  transform: scale(1.05);
}

.no-cover {
  width: 90px;
  height: 120px;
  display: flex;
  justify-content: center;
  align-items: center;
  background: #f5f5f5;
  border-radius: 8px;
  font-size: 40px;
}

.video-info {
  padding: 8px;
}

.task-id-cell {
  font-size: 13px;
  color: #1890ff;
  font-weight: 600;
  font-family: 'Courier New', monospace;
  display: inline-block;
  padding: 2px 8px;
  background: #f0f7ff;
  border-radius: 4px;
}

.video-platform-tag {
  margin-bottom: 8px;
}

.video-desc {
  color: #333;
  font-size: 14px;
  line-height: 1.6;
  margin-bottom: 8px;
  word-break: break-word;
  white-space: pre-wrap;
}

.video-desc-empty {
  color: #999;
  font-size: 13px;
  margin-bottom: 8px;
  font-style: italic;
}

.video-author {
  color: #666;
  font-size: 13px;
  line-height: 1.4;
}

.author-label {
  font-weight: 500;
  color: #888;
}

.author-id {
  color: #aaa;
  font-size: 12px;
}

/* 标签相关样式 */
.tags-container {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  max-width: 300px;
}

.tag-item {
  margin: 0;
}

.no-tags {
  color: #999;
  font-size: 13px;
  font-style: italic;
}

/* 表格行样式 */
:deep(.ant-table-tbody > tr) {
  vertical-align: top;
}

:deep(.ant-table-tbody > tr > td) {
  padding: 16px;
}

.batch-actions {
  margin-bottom: 16px;
  padding: 12px;
  background: #fafafa;
  border-radius: 4px;
  border: 1px solid #e8e8e8;
}
</style>
