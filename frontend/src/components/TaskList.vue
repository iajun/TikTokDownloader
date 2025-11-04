<template>
  <div>
    <div class="batch-header">
      <div class="select-all-section">
        <a-checkbox
          :indeterminate="indeterminate"
          :checked="checkAll"
          @change="onCheckAllChange"
        >
          全选
        </a-checkbox>
        <span class="select-hint">(仅可选择已完成或失败的任务)</span>
      </div>
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
            v-if="canBatchSummarize"
            type="primary"
            @click="handleBatchSummarize"
            :loading="batchSummarizeLoading"
            :icon="h(FileTextOutlined)"
          >
            批量总结
          </a-button>
          <a-dropdown v-if="canSendEmail && obsidianConfigured">
            <a-button
              type="primary"
              :loading="batchSendEmailLoading || batchSendToObsidianLoading"
              :icon="h(MailOutlined)"
            >
              批量发送 <DownOutlined />
            </a-button>
            <template #overlay>
              <a-menu>
                <a-menu-item 
                  key="email"
                  @click="handleBatchSendEmail"
                  :loading="batchSendEmailLoading"
                >
                  <MailOutlined /> 批量发送邮件
                </a-menu-item>
                <a-menu-item 
                  key="obsidian"
                  @click="handleBatchSendToObsidian"
                  :loading="batchSendToObsidianLoading"
                >
                  📝 批量发送到 Obsidian
                </a-menu-item>
              </a-menu>
            </template>
          </a-dropdown>
          <a-button
            v-else-if="canSendEmail"
            type="primary"
            @click="handleBatchSendEmail"
            :loading="batchSendEmailLoading"
            :icon="h(MailOutlined)"
          >
            批量发送邮件
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
    </div>
    
    <a-list
      :data-source="tasks"
      :loading="loading"
      :pagination="paginationConfigWithChange"
      item-layout="horizontal"
      class="task-list"
    >
      <template #renderItem="{ item }">
        <a-list-item class="task-list-item">
          <a-list-item-meta>
            <template #title>
              <div class="task-title">
                <a-checkbox
                  :checked="selectedRowKeys.includes(item.id)"
                  :disabled="item.status !== 'completed' && item.status !== 'failed'"
                  @change="(e: any) => handleCheckboxChange(e, item.id)"
                  class="task-checkbox"
                />
                <a-tag :color="item.platform === 'douyin' ? 'red' : 'blue'" size="small" class="platform-tag">
                  {{ item.platform === 'douyin' ? '抖音' : 'TikTok' }}
                </a-tag>
                <a-tag :color="getStatusColor(item.status)" size="small" class="status-tag">
                  {{ getStatusText(item.status) }}
                </a-tag>
                <span v-if="item.video?.desc" class="video-desc-text">{{ item.video.desc }}</span>
                <span v-else class="video-desc-empty">无描述</span>
              </div>
            </template>
            <template #description>
              <div class="task-description">
                <span v-if="item.video?.nickname" class="author-info">
                  作者：{{ item.video.nickname }}
                  <span v-if="item.video?.unique_id" class="author-id">(@{{ item.video.unique_id }})</span>
                </span>
                <a-divider type="vertical" />
                <a :href="item.url" target="_blank" class="task-url">{{ item.url }}</a>
                <a-divider type="vertical" v-if="item.status !== 'completed' && item.status !== 'failed'" />
                <a-progress
                  v-if="item.status !== 'completed' && item.status !== 'failed'"
                  :percent="item.progress"
                  :status="item.status === 'failed' ? 'exception' : undefined"
                  size="small"
                  :stroke-width="4"
                  class="task-progress"
                />
              </div>
            </template>
          </a-list-item-meta>
          <template #actions>
            <a-space>
              <a-button type="link" size="small" @click="viewTask(item)">查看</a-button>
              <template v-if="item.status === 'completed' && item.summary">
                <a-dropdown v-if="obsidianConfigured">
                  <a-button type="link" size="small">
                    发送 <DownOutlined />
                  </a-button>
                  <template #overlay>
                    <a-menu>
                      <a-menu-item 
                        key="email"
                        @click="sendEmail(item)"
                        :loading="sendEmailLoadingMap[item.id]"
                      >
                        <MailOutlined /> 发送邮件
                      </a-menu-item>
                      <a-menu-item 
                        key="obsidian"
                        @click="sendToObsidian(item)"
                        :loading="sendToObsidianLoadingMap[item.id]"
                      >
                        📝 发送到 Obsidian
                      </a-menu-item>
                    </a-menu>
                  </template>
                </a-dropdown>
                <a-button
                  v-else
                  type="link"
                  size="small"
                  @click="sendEmail(item)"
                  :loading="sendEmailLoadingMap[item.id]"
                >
                  发送邮件
                </a-button>
              </template>
              <a-button
                v-if="item.status !== 'completed'"
                type="link"
                size="small"
                @click="retryTask(item)"
                :loading="retryLoadingMap[item.id]"
              >
                重试
              </a-button>
              <a-button
                v-if="props.showRemoveFromFolder && props.folderId"
                type="link"
                size="small"
                danger
                @click="removeFromFolder(item)"
              >
                移除
              </a-button>
              <a-button
                v-if="item.status === 'completed' || item.status === 'failed'"
                type="link"
                size="small"
                danger
                @click="deleteTask(item)"
              >
                删除
              </a-button>
            </a-space>
          </template>
        </a-list-item>
      </template>
    </a-list>
    
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
import { ref, h, computed, watch, onMounted } from 'vue'
import { message, Modal } from 'ant-design-vue'
import type { TaskStatus } from '@/api/task'
import { useRouter } from 'vue-router'
import { ExclamationCircleOutlined } from '@ant-design/icons-vue'
import { retryTask as retryTaskApi, batchDeleteTasks, resummarizeTask, sendTaskEmail, getObsidianStatus, sendTaskToObsidian } from '@/api/task'
import { addTasksToCollection, removeTaskFromCollection, batchRemoveTasksFromCollection, getCollectionTree } from '@/api/collection'
import { StarOutlined, FileTextOutlined, MailOutlined, DownOutlined } from '@ant-design/icons-vue'

const router = useRouter()
const loading = ref(false)
const retryLoadingMap = ref<{ [key: number]: boolean }>({})
const selectedRowKeys = ref<number[]>([])
const batchDeleteLoading = ref(false)
const batchSummarizeLoading = ref(false)
const sendEmailLoadingMap = ref<{ [key: number]: boolean }>({})
const sendToObsidianLoadingMap = ref<{ [key: number]: boolean }>({})
const batchSendEmailLoading = ref(false)
const batchSendToObsidianLoading = ref(false)
const obsidianConfigured = ref(false)

// 添加到收藏夹相关状态
const addToCollectionModalVisible = ref(false)
const collectionTreeData = ref<any[]>([])
const selectedFolderId = ref<number | null>(null)
const addToCollectionLoading = ref(false)

interface Props {
  tasks: TaskStatus[]
  folderId?: number | null
  showRemoveFromFolder?: boolean
  pagination?: boolean | object
  total?: number
}

const props = defineProps<Props>()

const emit = defineEmits<{
  refresh: []
  change: [pagination: any]
}>()

// 可选择的任务（已完成或失败的任务）
const selectableTasks = computed(() => {
  return props.tasks.filter(t => t.status === 'completed' || t.status === 'failed')
})

// 全选相关状态
const checkAll = computed(() => {
  if (selectableTasks.value.length === 0) return false
  return selectedRowKeys.value.length === selectableTasks.value.length &&
    selectableTasks.value.every(t => selectedRowKeys.value.includes(t.id))
})

const indeterminate = computed(() => {
  const selectedCount = selectedRowKeys.value.length
  const selectableCount = selectableTasks.value.length
  return selectedCount > 0 && selectedCount < selectableCount
})

// 处理全选
const onCheckAllChange = (e: any) => {
  if (e.target.checked) {
    // 全选所有可选择的任务
    selectedRowKeys.value = selectableTasks.value.map(t => t.id)
  } else {
    // 取消全选
    selectedRowKeys.value = []
  }
}

// 判断是否可以批量总结（选中的任务中有已完成的任务）
const canBatchSummarize = computed(() => {
  return selectedRowKeys.value.some(id => {
    const task = props.tasks.find(t => t.id === id)
    return task && task.status === 'completed' && task.transcription
  })
})

// 判断是否可以批量发送邮件（选中的任务中有已完成且有总结的任务）
const canSendEmail = computed(() => {
  return selectedRowKeys.value.some(id => {
    const task = props.tasks.find(t => t.id === id)
    return task && task.status === 'completed' && task.summary
  })
})

// 处理复选框变化
const handleCheckboxChange = (e: any, taskId: number) => {
  if (e.target.checked) {
    if (!selectedRowKeys.value.includes(taskId)) {
      selectedRowKeys.value.push(taskId)
    }
  } else {
    selectedRowKeys.value = selectedRowKeys.value.filter(id => id !== taskId)
  }
}

// 分页配置
const paginationConfig = computed(() => {
  if (props.pagination === false) {
    return false
  }
  
  if (typeof props.pagination === 'object') {
    return {
      ...props.pagination,
      showTotal: (total: number) => `共 ${total} 条`,
      pageSizeOptions: ['10', '20', '50', '100']
    }
  }
  
  if (props.pagination === true || props.pagination !== undefined) {
    return {
      total: props.total || props.tasks.length,
      showSizeChanger: true,
      showQuickJumper: true,
      showTotal: (total: number) => `共 ${total} 条`,
      pageSizeOptions: ['10', '20', '50', '100']
    }
  }
  
  return false
})

// 分页配置（带变化事件）
const paginationConfigWithChange = computed(() => {
  const config = paginationConfig.value
  if (!config) return false
  
  return {
    ...config,
    onChange: (page: number, pageSize: number) => {
      emit('change', { page, pageSize })
    }
  }
})

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

const viewTask = (task: TaskStatus) => {
  router.push(`/detail/${task.id}`)
}

const retryTask = async (task: TaskStatus) => {
  retryLoadingMap.value[task.id] = true
  try {
    const response = await retryTaskApi(task.id)
    if (response.success) {
      message.success('任务已重新提交，将开始处理')
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

// 批量总结
const handleBatchSummarize = () => {
  // 筛选出可以总结的任务（已完成且有转录内容）
  const summarizableTasks = selectedRowKeys.value.filter(id => {
    const task = props.tasks.find(t => t.id === id)
    return task && task.status === 'completed' && task.transcription
  })
  
  if (summarizableTasks.length === 0) {
    message.warning('所选任务中没有可以总结的任务（需要已完成且有转录内容）')
    return
  }
  
  Modal.confirm({
    title: '确认批量总结',
    icon: h(ExclamationCircleOutlined),
    content: `确定要为选中的 ${summarizableTasks.length} 个已完成任务重新生成总结吗？此操作将覆盖现有总结。`,
    okText: '开始总结',
    okType: 'primary',
    async onOk() {
      batchSummarizeLoading.value = true
      let successCount = 0
      let failCount = 0
      
      try {
        // 并发控制：最多同时处理5个请求
        const CONCURRENT_LIMIT = 5
        const tasks = [...summarizableTasks]
        
        // 分批处理任务
        for (let i = 0; i < tasks.length; i += CONCURRENT_LIMIT) {
          const batch = tasks.slice(i, i + CONCURRENT_LIMIT)
          const batchPromises = batch.map(async (taskId) => {
            try {
              const response = await resummarizeTask(taskId)
              return { success: response.success, taskId }
            } catch (error: any) {
              console.error(`Task ${taskId} summarization failed:`, error)
              return { success: false, taskId }
            }
          })
          
          const batchResults = await Promise.all(batchPromises)
          batchResults.forEach(result => {
            if (result.success) {
              successCount++
            } else {
              failCount++
            }
          })
        }
        
        if (successCount > 0) {
          message.success(`成功提交 ${successCount} 个任务的总结请求${failCount > 0 ? `，${failCount} 个任务失败` : ''}`)
          selectedRowKeys.value = []
          // 延迟刷新，让用户看到反馈
          setTimeout(() => {
            emit('refresh')
          }, 1000)
        } else {
          message.error('所有任务的总结请求都失败了')
        }
      } catch (error: any) {
        message.error(error.response?.data?.detail || error.message || '批量总结失败')
      } finally {
        batchSummarizeLoading.value = false
      }
    },
  })
}

// 检查 Obsidian 配置
const checkObsidianConfig = async () => {
  try {
    const response = await getObsidianStatus()
    if (response.success && response.data) {
      obsidianConfigured.value = response.data.is_configured || false
    }
  } catch (error) {
    console.error('Failed to check Obsidian status:', error)
    obsidianConfigured.value = false
  }
}

// 发送单个任务邮件
const sendEmail = async (task: TaskStatus) => {
  if (!task.summary) {
    message.warning('该任务没有总结内容，无法发送邮件')
    return
  }
  
  sendEmailLoadingMap.value[task.id] = true
  try {
    const response = await sendTaskEmail(task.id)
    if (response.success) {
      const { success_count, total_emails } = response.data
      message.success(`邮件已发送到 ${success_count}/${total_emails} 个订阅邮箱`)
    } else {
      message.error(response.message || '发送邮件失败')
    }
  } catch (error: any) {
    const errorMessage = error.response?.data?.detail || error.message || '发送邮件失败'
    message.error(errorMessage)
  } finally {
    sendEmailLoadingMap.value[task.id] = false
  }
}

// 发送单个任务到 Obsidian
const sendToObsidian = async (task: TaskStatus) => {
  if (!task.summary) {
    message.warning('该任务没有总结内容，无法发送到 Obsidian')
    return
  }
  
  sendToObsidianLoadingMap.value[task.id] = true
  try {
    const response = await sendTaskToObsidian(task.id)
    if (response.success) {
      message.success(`总结已保存到 Obsidian: ${response.data.file_path}`)
    } else {
      message.error(response.message || '发送到 Obsidian 失败')
    }
  } catch (error: any) {
    const errorMessage = error.response?.data?.detail || error.message || '发送到 Obsidian 失败'
    message.error(errorMessage)
  } finally {
    sendToObsidianLoadingMap.value[task.id] = false
  }
}

// 批量发送邮件
const handleBatchSendEmail = () => {
  // 筛选出可以发送邮件的任务（已完成且有总结）
  const sendableTasks = selectedRowKeys.value.filter(id => {
    const task = props.tasks.find(t => t.id === id)
    return task && task.status === 'completed' && task.summary
  })
  
  if (sendableTasks.length === 0) {
    message.warning('所选任务中没有可以发送邮件的任务（需要已完成且有总结）')
    return
  }
  
  Modal.confirm({
    title: '确认批量发送邮件',
    icon: h(ExclamationCircleOutlined),
    content: `确定要向所有订阅邮箱发送选中的 ${sendableTasks.length} 个任务的总结邮件吗？`,
    okText: '发送',
    okType: 'primary',
    async onOk() {
      batchSendEmailLoading.value = true
      let successCount = 0
      let failCount = 0
      let totalEmails = 0
      
      try {
        // 并发控制：最多同时处理5个请求
        const CONCURRENT_LIMIT = 5
        const tasks = [...sendableTasks]
        
        // 分批处理任务
        for (let i = 0; i < tasks.length; i += CONCURRENT_LIMIT) {
          const batch = tasks.slice(i, i + CONCURRENT_LIMIT)
          const batchPromises = batch.map(async (taskId) => {
            try {
              const response = await sendTaskEmail(taskId)
              if (response.success) {
                totalEmails += response.data.total_emails
                return { 
                  success: true, 
                  taskId,
                  successCount: response.data.success_count,
                  totalEmails: response.data.total_emails
                }
              } else {
                return { success: false, taskId }
              }
            } catch (error: any) {
              console.error(`Task ${taskId} email sending failed:`, error)
              return { success: false, taskId }
            }
          })
          
          const batchResults = await Promise.all(batchPromises)
          batchResults.forEach(result => {
            if (result.success) {
              successCount++
            } else {
              failCount++
            }
          })
        }
        
        if (successCount > 0) {
          message.success(
            `成功发送 ${successCount} 个任务的邮件${failCount > 0 ? `，${failCount} 个任务失败` : ''}，共发送到 ${totalEmails} 个邮箱`
          )
          selectedRowKeys.value = []
          emit('refresh')
        } else {
          message.error('所有任务的邮件发送都失败了')
        }
      } catch (error: any) {
        message.error(error.response?.data?.detail || error.message || '批量发送邮件失败')
      } finally {
        batchSendEmailLoading.value = false
      }
    },
  })
}

// 批量发送到 Obsidian
const handleBatchSendToObsidian = () => {
  // 筛选出可以发送到 Obsidian 的任务（已完成且有总结）
  const sendableTasks = selectedRowKeys.value.filter(id => {
    const task = props.tasks.find(t => t.id === id)
    return task && task.status === 'completed' && task.summary
  })
  
  if (sendableTasks.length === 0) {
    message.warning('所选任务中没有可以发送到 Obsidian 的任务（需要已完成且有总结）')
    return
  }
  
  Modal.confirm({
    title: '确认批量发送到 Obsidian',
    icon: h(ExclamationCircleOutlined),
    content: `确定要将选中的 ${sendableTasks.length} 个任务的总结发送到 Obsidian 吗？`,
    okText: '发送',
    okType: 'primary',
    async onOk() {
      batchSendToObsidianLoading.value = true
      let successCount = 0
      let failCount = 0
      
      try {
        // 并发控制：最多同时处理5个请求
        const CONCURRENT_LIMIT = 5
        const tasks = [...sendableTasks]
        
        // 分批处理任务
        for (let i = 0; i < tasks.length; i += CONCURRENT_LIMIT) {
          const batch = tasks.slice(i, i + CONCURRENT_LIMIT)
          const batchPromises = batch.map(async (taskId) => {
            try {
              const response = await sendTaskToObsidian(taskId)
              return { 
                success: response.success, 
                taskId,
                filePath: response.data?.file_path
              }
            } catch (error: any) {
              console.error(`Task ${taskId} Obsidian sync failed:`, error)
              return { success: false, taskId }
            }
          })
          
          const batchResults = await Promise.all(batchPromises)
          batchResults.forEach(result => {
            if (result.success) {
              successCount++
            } else {
              failCount++
            }
          })
        }
        
        if (successCount > 0) {
          message.success(
            `成功发送 ${successCount} 个任务的总结到 Obsidian${failCount > 0 ? `，${failCount} 个任务失败` : ''}`
          )
          selectedRowKeys.value = []
          emit('refresh')
        } else {
          message.error('所有任务的 Obsidian 同步都失败了')
        }
      } catch (error: any) {
        message.error(error.response?.data?.detail || error.message || '批量发送到 Obsidian 失败')
      } finally {
        batchSendToObsidianLoading.value = false
      }
    },
  })
}

// 监听 tasks 变化，清除不可用的选中项
watch(() => props.tasks, () => {
  // 移除已不在列表中或不可选择的任务
  selectedRowKeys.value = selectedRowKeys.value.filter(id => {
    const task = props.tasks.find(t => t.id === id)
    return task && (task.status === 'completed' || task.status === 'failed')
  })
}, { deep: true })

// 组件挂载时检查 Obsidian 配置
onMounted(() => {
  checkObsidianConfig()
})
</script>

<style scoped>
.task-list {
  background: #fff;
}

.task-list-item {
  padding: 8px 16px !important;
  border-bottom: 1px solid #f0f0f0;
  transition: background-color 0.2s;
}

.task-list-item:hover {
  background-color: #fafafa;
}

.task-title {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.task-checkbox {
  margin-right: 4px;
}

.platform-tag,
.status-tag {
  margin: 0;
  flex-shrink: 0;
}

.video-desc-text {
  color: #333;
  font-size: 13px;
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.video-desc-empty {
  color: #999;
  font-size: 13px;
  font-style: italic;
}

.task-description {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  font-size: 11px;
  color: #666;
  margin-top: 2px;
}

.author-info {
  color: #666;
  white-space: nowrap;
}

.author-id {
  color: #999;
  margin-left: 4px;
}

.task-url {
  color: #1890ff;
  max-width: 300px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  display: inline-block;
}

.task-progress {
  width: 120px;
  flex-shrink: 0;
}

.batch-header {
  margin-bottom: 12px;
}

.select-all-section {
  padding: 8px 12px;
  background: #fafafa;
  border-radius: 4px;
  border: 1px solid #e8e8e8;
  margin-bottom: 8px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.select-hint {
  font-size: 12px;
  color: #999;
}

.batch-actions {
  padding: 8px 12px;
  background: #fafafa;
  border-radius: 4px;
  border: 1px solid #e8e8e8;
}

:deep(.ant-list-item-meta-title) {
  margin-bottom: 2px !important;
}

:deep(.ant-list-item-meta-description) {
  margin-bottom: 0 !important;
}

:deep(.ant-list-item-action) {
  margin-left: 12px;
}

:deep(.ant-list-item-action > li) {
  padding: 0 2px;
}

:deep(.ant-list-item-meta-content) {
  flex: 1;
  min-width: 0;
}

:deep(.ant-list-item-meta) {
  margin-bottom: 0;
}
</style>

