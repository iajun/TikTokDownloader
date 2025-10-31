<template>
  <div class="settings-container">
    <a-card>
      <template #title>
        <h2>⚙️ 系统设置</h2>
      </template>
      
      <a-tabs v-model:activeKey="activeTab">
        <a-tab-pane key="prompts" tab="提示词管理">
          <div class="prompts-management">
            <a-space style="margin-bottom: 24px; width: 100%;" :size="20">
              <a-button type="primary" @click="showCreateModal">
                <template #icon>
                  <component :is="h(PlusOutlined)" />
                </template>
                新建提示词
              </a-button>
            </a-space>
            
            <a-table
              :columns="promptColumns"
              :data-source="prompts"
              :pagination="false"
              row-key="id"
            >
              <template #bodyCell="{ column, record }">
                <template v-if="column.key === 'is_default'">
                  <a-tag v-if="record.is_default === 1" color="green">默认</a-tag>
                </template>
                <template v-if="column.key === 'content'">
                  <span class="content-preview">{{ record.content.substring(0, 100) }}{{ record.content.length > 100 ? '...' : '' }}</span>
                </template>
                <template v-if="column.key === 'actions'">
                  <a-space>
                    <a-button size="small" @click="showEditModal(record)">编辑</a-button>
                    <a-button 
                      size="small" 
                      v-if="record.is_default !== 1" 
                      @click="setAsDefault(record.id)"
                    >
                      设为默认
                    </a-button>
                    <a-button 
                      size="small" 
                      danger 
                      v-if="record.is_default !== 1"
                      @click="handleDelete(record)"
                    >
                      删除
                    </a-button>
                  </a-space>
                </template>
              </template>
            </a-table>
          </div>
        </a-tab-pane>
        
        <a-tab-pane key="ai-methods" tab="AI方法管理">
          <div class="ai-methods-settings">
            <a-alert
              type="info"
              message="AI方法配置说明"
              description="选择不同的AI总结方式，支持API方式（DeepSeek）和浏览器方式（ChatGPT、腾讯元宝）。"
              show-icon
              style="margin-bottom: 24px;"
            />
            
            <a-space style="margin-bottom: 24px; width: 100%;" :size="20">
              <a-button type="primary" @click="showCreateAIMethodModal">
                <template #icon>
                  <component :is="h(PlusOutlined)" />
                </template>
                添加AI方法
              </a-button>
            </a-space>
            
            <a-table
              :columns="aiMethodColumns"
              :data-source="aiMethods"
              :pagination="false"
              row-key="id"
            >
              <template #bodyCell="{ column, record }">
                <template v-if="column.key === 'is_active'">
                  <a-tag v-if="record.is_active === 1" color="green">活跃</a-tag>
                  <a-tag v-else color="default">未激活</a-tag>
                </template>
                <template v-if="column.key === 'method_type'">
                  <a-tag :color="record.method_type === 'api' ? 'blue' : 'orange'">
                    {{ record.method_type === 'api' ? 'API方式' : '浏览器方式' }}
                  </a-tag>
                </template>
                <template v-if="column.key === 'actions'">
                  <a-space>
                    <a-button size="small" @click="showEditAIMethodModal(record)">编辑</a-button>
                    <a-button 
                      size="small" 
                      v-if="record.is_active !== 1" 
                      @click="setActiveAIMethodAction(record.id)"
                    >
                      设为活跃
                    </a-button>
                    <a-button 
                      size="small" 
                      danger 
                      @click="handleDeleteAIMethod(record)"
                    >
                      删除
                    </a-button>
                  </a-space>
                </template>
              </template>
            </a-table>
          </div>
        </a-tab-pane>
        
        <a-tab-pane key="ai-params" tab="AI参数设置">
          <div class="ai-params-settings">
            <a-alert
              type="info"
              message="AI参数配置说明"
              description="调整 AI 生成总结时的参数，影响生成文本的质量和随机性。"
              show-icon
              style="margin-bottom: 24px;"
            />
            
            <a-form :model="aiParamsForm" layout="vertical" style="max-width: 600px;">
              <a-form-item label="模型名称" help="使用的 AI 模型">
                <a-input v-model:value="aiParamsForm.model" placeholder="deepseek-chat" />
              </a-form-item>
              
              <a-form-item label="最大 Token 数" help="生成文本的最大 token 数，值越大允许生成的文本越长">
                <a-input-number 
                  v-model:value="aiParamsForm.max_tokens" 
                  :min="100" 
                  :max="8000"
                  :step="100"
                  style="width: 100%;"
                />
              </a-form-item>
              
              <a-form-item label="Temperature (随机性)" help="控制生成的随机性，0-2之间。值越高越随机，值越低越保守">
                <a-slider 
                  v-model:value="aiParamsForm.temperature"
                  :min="0"
                  :max="2"
                  :step="0.1"
                  :marks="{ 0: '0 (保守)', 0.7: '0.7', 1: '1', 2: '2 (随机)' }"
                />
                <div style="margin-top: 8px;">
                  <a-input-number 
                    v-model:value="aiParamsForm.temperature"
                    :min="0" 
                    :max="2"
                    :step="0.1"
                    style="width: 100%;"
                  />
                </div>
              </a-form-item>
              
              <a-form-item label="系统提示词" help="AI 的角色定义">
                <a-textarea
                  v-model:value="aiParamsForm.system_prompt"
                  placeholder="输入系统提示词"
                  :rows="3"
                />
              </a-form-item>
              
              <a-form-item>
                <a-button type="primary" @click="handleSaveAIParams" :loading="savingParams">
                  <template #icon>
                    <component :is="h(SaveOutlined)" />
                  </template>
                  保存设置
                </a-button>
                <a-button @click="handleResetAIParams" style="margin-left: 8px;" :loading="loadingParams">
                  <template #icon>
                    <component :is="h(ReloadOutlined)" />
                  </template>
                  恢复默认
                </a-button>
              </a-form-item>
            </a-form>
          </div>
        </a-tab-pane>
        
        <a-tab-pane key="email-subscriptions" tab="邮箱订阅">
          <div class="email-subscriptions-management">
            <a-alert
              type="info"
              message="邮箱订阅说明"
              description="订阅邮箱后，当视频总结完成时，系统会自动将视频信息和总结文档发送到您的邮箱。"
              show-icon
              style="margin-bottom: 24px;"
            />
            
            <a-space style="margin-bottom: 24px; width: 100%;" :size="20">
              <a-button type="primary" @click="showCreateEmailSubscriptionModal">
                <template #icon>
                  <component :is="h(PlusOutlined)" />
                </template>
                添加订阅邮箱
              </a-button>
            </a-space>
            
            <a-table
              :columns="emailSubscriptionColumns"
              :data-source="emailSubscriptions"
              :pagination="false"
              row-key="id"
              :loading="loadingEmailSubscriptions"
            >
              <template #bodyCell="{ column, record }">
                <template v-if="column.key === 'is_active'">
                  <a-tag v-if="record.is_active" color="green">已激活</a-tag>
                  <a-tag v-else color="default">未激活</a-tag>
                </template>
                <template v-if="column.key === 'created_at'">
                  <span>{{ formatDate(record.created_at) }}</span>
                </template>
                <template v-if="column.key === 'actions'">
                  <a-space>
                    <a-button 
                      size="small" 
                      @click="toggleEmailSubscriptionStatus(record)"
                    >
                      {{ record.is_active ? '停用' : '启用' }}
                    </a-button>
                    <a-button 
                      size="small" 
                      danger 
                      @click="handleDeleteEmailSubscription(record)"
                    >
                      删除
                    </a-button>
                  </a-space>
                </template>
              </template>
            </a-table>
          </div>
        </a-tab-pane>
        
        <a-tab-pane key="info" tab="关于">
          <a-descriptions :column="1" bordered>
            <a-descriptions-item label="服务名称">
              AI Video Summarizer
            </a-descriptions-item>
            <a-descriptions-item label="版本">
              1.0.0
            </a-descriptions-item>
            <a-descriptions-item label="功能">
              抖音/TikTok 视频 AI 智能总结服务
            </a-descriptions-item>
          </a-descriptions>
        </a-tab-pane>
      </a-tabs>
    </a-card>
    
    <!-- 提示词编辑/创建模态框 -->
    <a-modal
      v-model:visible="modalVisible"
      :title="modalTitle"
      @ok="handleSavePromptModal"
      :confirm-loading="saving"
      width="800px"
    >
      <a-form :model="promptModalForm" layout="vertical">
        <a-form-item label="提示词名称" required>
          <a-input v-model:value="promptModalForm.name" placeholder="请输入提示词名称" />
        </a-form-item>
        
        <a-form-item label="描述（可选）">
          <a-input v-model:value="promptModalForm.description" placeholder="请输入描述" />
        </a-form-item>
        
        <a-form-item label="提示词内容" required>
          <a-textarea
            v-model:value="promptModalForm.content"
            placeholder="请输入提示词内容，使用 {text} 占位符代表视频转录文本"
            :rows="20"
            class="prompt-textarea"
          />
        </a-form-item>
      </a-form>
    </a-modal>
    
    <!-- AI方法编辑/创建模态框 -->
    <a-modal
      v-model:visible="aiMethodModalVisible"
      :title="aiMethodModalTitle"
      @ok="handleSaveAIMethodModal"
      :confirm-loading="saving"
      width="700px"
    >
      <a-form :model="aiMethodModalForm" layout="vertical">
        <a-form-item label="方法名称（唯一标识）" required>
          <a-input 
            v-model:value="aiMethodModalForm.name" 
            placeholder="例如: deepseek, chatgpt, yuanbao"
            :disabled="isEditingAIMethod"
          />
        </a-form-item>
        
        <a-form-item label="显示名称" required>
          <a-input v-model:value="aiMethodModalForm.display_name" placeholder="例如: DeepSeek API" />
        </a-form-item>
        
        <a-form-item label="API密钥（API方式）">
          <a-input-password v-model:value="aiMethodModalForm.api_key" placeholder="用于API方式的AI密钥" />
        </a-form-item>
        
        <a-form-item label="Cookies（浏览器方式）">
          <a-textarea
            v-model:value="aiMethodModalForm.cookies"
            placeholder="用于浏览器方式的Cookies（JSON格式或Cookie字符串）"
            :rows="4"
          />
        </a-form-item>
        
        <a-form-item label="基础URL">
          <a-input v-model:value="aiMethodModalForm.base_url" placeholder="可选，自定义API基础URL" />
        </a-form-item>
        
        <a-form-item label="描述">
          <a-textarea v-model:value="aiMethodModalForm.description" placeholder="描述此AI方法的用途" :rows="2" />
        </a-form-item>
      </a-form>
    </a-modal>
    
    <!-- 邮箱订阅编辑/创建模态框 -->
    <a-modal
      v-model:visible="emailSubscriptionModalVisible"
      title="添加订阅邮箱"
      @ok="handleSaveEmailSubscriptionModal"
      :confirm-loading="savingEmailSubscription"
      width="500px"
    >
      <a-form :model="emailSubscriptionForm" layout="vertical">
        <a-form-item label="邮箱地址" required>
          <a-input 
            v-model:value="emailSubscriptionForm.email" 
            placeholder="请输入邮箱地址"
            type="email"
          />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, h } from 'vue'
import { message, Modal } from 'ant-design-vue'
import { 
  SaveOutlined, 
  ReloadOutlined, 
  FileTextOutlined, 
  PlusOutlined,
  EditOutlined
} from '@ant-design/icons-vue'
import { 
  getPromptTemplate, 
  updateSetting, 
  getSetting,
  listPrompts,
  createPrompt,
  updatePrompt,
  deletePrompt,
  setDefaultPrompt,
  type Prompt,
  type CreatePromptRequest,
  type UpdatePromptRequest
} from '@/api/prompt'
import { 
  listAIMethods,
  createAIMethod,
  updateAIMethod,
  deleteAIMethod,
  setActiveAIMethod,
  type AIMethod,
  type CreateAIMethodRequest,
  type UpdateAIMethodRequest
} from '@/api/ai-method'
import {
  getAllEmailSubscriptions,
  createEmailSubscription,
  updateEmailSubscription,
  deleteEmailSubscription,
  type EmailSubscription as EmailSubscriptionType,
  type EmailSubscriptionCreateRequest,
  type EmailSubscriptionUpdateRequest
} from '@/api/emailSubscription'

const activeTab = ref('prompts')
const saving = ref(false)
const loading = ref(false)
const savingParams = ref(false)
const loadingParams = ref(false)
const modalVisible = ref(false)
const modalTitle = ref('新建提示词')
const isEditing = ref(false)
const currentPromptId = ref<number | null>(null)

const prompts = ref<Prompt[]>([])
const aiMethods = ref<(AIMethod & { method_type: string })[]>([])
const emailSubscriptions = ref<EmailSubscriptionType[]>([])
const loadingEmailSubscriptions = ref(false)
const emailSubscriptionModalVisible = ref(false)
const savingEmailSubscription = ref(false)
const emailSubscriptionForm = ref({
  email: ''
})

const emailSubscriptionColumns = [
  {
    title: '邮箱地址',
    dataIndex: 'email',
    key: 'email',
  },
  {
    title: '状态',
    dataIndex: 'is_active',
    key: 'is_active',
    width: 100,
  },
  {
    title: '创建时间',
    dataIndex: 'created_at',
    key: 'created_at',
    width: 180,
  },
  {
    title: '操作',
    key: 'actions',
    width: 200,
  },
]

const aiMethodColumns = [
  {
    title: '名称',
    dataIndex: 'name',
    key: 'name',
  },
  {
    title: '显示名称',
    dataIndex: 'display_name',
    key: 'display_name',
  },
  {
    title: '类型',
    dataIndex: 'method_type',
    key: 'method_type',
  },
  {
    title: '状态',
    dataIndex: 'is_active',
    key: 'is_active',
    width: 100,
  },
  {
    title: '操作',
    key: 'actions',
    width: 300,
  },
]

const promptColumns = [
  {
    title: '名称',
    dataIndex: 'name',
    key: 'name',
  },
  {
    title: '描述',
    dataIndex: 'description',
    key: 'description',
  },
  {
    title: '内容预览',
    dataIndex: 'content',
    key: 'content',
  },
  {
    title: '默认',
    dataIndex: 'is_default',
    key: 'is_default',
    width: 100,
  },
  {
    title: '操作',
    key: 'actions',
    width: 200,
  },
]

const promptModalForm = ref({
  name: '',
  description: '',
  content: ''
})

const aiParamsForm = ref({
  model: 'deepseek-chat',
  max_tokens: 2000,
  temperature: 0.7,
  system_prompt: '你是一个有上进心爱思考的年轻人，你习惯在抖音视频中学习知识，并擅长总结和分析视频内容。'
})

const aiMethodModalVisible = ref(false)
const aiMethodModalTitle = ref('添加AI方法')
const isEditingAIMethod = ref(false)
const currentAIMethodId = ref<number | null>(null)
const aiMethodModalForm = ref({
  name: '',
  display_name: '',
  api_key: '',
  cookies: '',
  base_url: '',
  description: ''
})

const loadPrompts = async () => {
  loading.value = true
  try {
    const response = await listPrompts()
    if (response.success && response.data) {
      prompts.value = response.data
    }
  } catch (error: any) {
    message.error(error.message || '加载提示词失败')
  } finally {
    loading.value = false
  }
}

const showCreateModal = () => {
  modalTitle.value = '新建提示词'
  isEditing.value = false
  currentPromptId.value = null
  promptModalForm.value = {
    name: '',
    description: '',
    content: ''
  }
  modalVisible.value = true
}

const showEditModal = (record: Prompt) => {
  modalTitle.value = '编辑提示词'
  isEditing.value = true
  currentPromptId.value = record.id
  promptModalForm.value = {
    name: record.name,
    description: record.description || '',
    content: record.content
  }
  modalVisible.value = true
}

const handleSavePromptModal = async () => {
  if (!promptModalForm.value.name.trim()) {
    message.warning('请输入提示词名称')
    return
  }
  if (!promptModalForm.value.content.trim()) {
    message.warning('请输入提示词内容')
    return
  }
  
  saving.value = true
  try {
    if (isEditing.value && currentPromptId.value) {
      // 更新
      const data: UpdatePromptRequest = {
        name: promptModalForm.value.name,
        content: promptModalForm.value.content,
        description: promptModalForm.value.description
      }
      await updatePrompt(currentPromptId.value, data)
      message.success('提示词已更新')
    } else {
      // 创建
      const data: CreatePromptRequest = {
        name: promptModalForm.value.name,
        content: promptModalForm.value.content,
        description: promptModalForm.value.description
      }
      await createPrompt(data)
      message.success('提示词已创建')
    }
    modalVisible.value = false
    await loadPrompts()
  } catch (error: any) {
    message.error(error.response?.data?.detail || error.message || '操作失败')
  } finally {
    saving.value = false
  }
}

const setAsDefault = async (promptId: number) => {
  try {
    await setDefaultPrompt(promptId)
    message.success('已设置为默认提示词')
    await loadPrompts()
  } catch (error: any) {
    message.error(error.response?.data?.detail || error.message || '设置失败')
  }
}

const handleDelete = (record: Prompt) => {
  Modal.confirm({
    title: '确认删除',
    content: `确定要删除提示词 "${record.name}" 吗？`,
    okText: '删除',
    okType: 'danger',
    cancelText: '取消',
    onOk: async () => {
      try {
        await deletePrompt(record.id)
        message.success('提示词已删除')
        await loadPrompts()
      } catch (error: any) {
        message.error(error.response?.data?.detail || error.message || '删除失败')
      }
    },
  })
}

const loadAIParams = async () => {
  loadingParams.value = true
  try {
    const params = ['ai_model', 'ai_max_tokens', 'ai_temperature', 'ai_system_prompt']
    for (const key of params) {
      const response = await getSetting(key)
      if (response.success && response.data) {
        const value = response.data.value
        switch (key) {
          case 'ai_model':
            aiParamsForm.value.model = value
            break
          case 'ai_max_tokens':
            aiParamsForm.value.max_tokens = parseInt(value) || 2000
            break
          case 'ai_temperature':
            aiParamsForm.value.temperature = parseFloat(value) || 0.7
            break
          case 'ai_system_prompt':
            aiParamsForm.value.system_prompt = value
            break
        }
      }
    }
  } catch (error: any) {
    message.error(error.message || '加载失败')
  } finally {
    loadingParams.value = false
  }
}

const handleSaveAIParams = async () => {
  savingParams.value = true
  try {
    // 保存所有 AI 参数
    await updateSetting('ai_model', { value: aiParamsForm.value.model })
    await updateSetting('ai_max_tokens', { value: String(aiParamsForm.value.max_tokens) })
    await updateSetting('ai_temperature', { value: String(aiParamsForm.value.temperature) })
    await updateSetting('ai_system_prompt', { value: aiParamsForm.value.system_prompt })
    
    message.success('AI参数配置已保存')
  } catch (error: any) {
    message.error(error.response?.data?.detail || error.message || '保存失败')
  } finally {
    savingParams.value = false
  }
}

const handleResetAIParams = async () => {
  loadingParams.value = true
  try {
    // 恢复默认值
    aiParamsForm.value = {
      model: 'deepseek-chat',
      max_tokens: 2000,
      temperature: 0.7,
      system_prompt: '你是一个有上进心爱思考的年轻人，你习惯在抖音视频中学习知识，并擅长总结和分析视频内容。'
    }
    message.success('已恢复默认值')
  } catch (error: any) {
    message.error(error.message || '加载失败')
  } finally {
    loadingParams.value = false
  }
}

const loadAIMethods = async () => {
  loading.value = true
  try {
    const response = await listAIMethods()
    if (response.success && response.data) {
      aiMethods.value = response.data.map(method => ({
        ...method,
        method_type: method.name === 'deepseek' ? 'api' : 'browser'
      }))
    }
  } catch (error: any) {
    message.error(error.message || '加载AI方法失败')
  } finally {
    loading.value = false
  }
}

const showCreateAIMethodModal = () => {
  aiMethodModalTitle.value = '添加AI方法'
  isEditingAIMethod.value = false
  currentAIMethodId.value = null
  aiMethodModalForm.value = {
    name: '',
    display_name: '',
    api_key: '',
    cookies: '',
    base_url: '',
    description: ''
  }
  aiMethodModalVisible.value = true
}

const showEditAIMethodModal = (record: AIMethod) => {
  aiMethodModalTitle.value = '编辑AI方法'
  isEditingAIMethod.value = true
  currentAIMethodId.value = record.id
  aiMethodModalForm.value = {
    name: record.name,
    display_name: record.display_name,
    api_key: record.api_key || '',
    cookies: record.cookies || '',
    base_url: record.base_url || '',
    description: record.description || ''
  }
  aiMethodModalVisible.value = true
}

const handleSaveAIMethodModal = async () => {
  if (!aiMethodModalForm.value.name.trim() || !aiMethodModalForm.value.display_name.trim()) {
    message.warning('请填写名称和显示名称')
    return
  }
  
  saving.value = true
  try {
    if (isEditingAIMethod.value && currentAIMethodId.value) {
      const data: UpdateAIMethodRequest = {
        display_name: aiMethodModalForm.value.display_name,
        api_key: aiMethodModalForm.value.api_key,
        cookies: aiMethodModalForm.value.cookies,
        base_url: aiMethodModalForm.value.base_url,
        description: aiMethodModalForm.value.description
      }
      await updateAIMethod(currentAIMethodId.value, data)
      message.success('AI方法已更新')
    } else {
      const data: CreateAIMethodRequest = {
        name: aiMethodModalForm.value.name,
        display_name: aiMethodModalForm.value.display_name,
        api_key: aiMethodModalForm.value.api_key || undefined,
        cookies: aiMethodModalForm.value.cookies || undefined,
        base_url: aiMethodModalForm.value.base_url || undefined,
        description: aiMethodModalForm.value.description || undefined
      }
      await createAIMethod(data)
      message.success('AI方法已创建')
    }
    aiMethodModalVisible.value = false
    await loadAIMethods()
  } catch (error: any) {
    message.error(error.response?.data?.detail || error.message || '操作失败')
  } finally {
    saving.value = false
  }
}

const setActiveAIMethodAction = async (methodId: number) => {
  try {
    await setActiveAIMethod(methodId)
    message.success('已设置为主要AI方法')
    await loadAIMethods()
  } catch (error: any) {
    message.error(error.response?.data?.detail || error.message || '设置失败')
  }
}

const handleDeleteAIMethod = (record: AIMethod) => {
  Modal.confirm({
    title: '确认删除',
    content: `确定要删除AI方法 "${record.display_name}" 吗？`,
    okText: '删除',
    okType: 'danger',
    cancelText: '取消',
    onOk: async () => {
      try {
        await deleteAIMethod(record.id)
        message.success('AI方法已删除')
        await loadAIMethods()
      } catch (error: any) {
        message.error(error.response?.data?.detail || error.message || '删除失败')
      }
    },
  })
}

const formatDate = (dateStr: string) => {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  return date.toLocaleString('zh-CN')
}

const loadEmailSubscriptions = async () => {
  loadingEmailSubscriptions.value = true
  try {
    const response = await getAllEmailSubscriptions()
    if (response.success && response.data) {
      emailSubscriptions.value = response.data
    }
  } catch (error: any) {
    message.error(error.message || '加载邮箱订阅失败')
  } finally {
    loadingEmailSubscriptions.value = false
  }
}

const showCreateEmailSubscriptionModal = () => {
  emailSubscriptionForm.value = {
    email: ''
  }
  emailSubscriptionModalVisible.value = true
}

const handleSaveEmailSubscriptionModal = async () => {
  if (!emailSubscriptionForm.value.email.trim()) {
    message.warning('请输入邮箱地址')
    return
  }
  
  // 简单的邮箱格式验证
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
  if (!emailRegex.test(emailSubscriptionForm.value.email)) {
    message.warning('请输入有效的邮箱地址')
    return
  }
  
  savingEmailSubscription.value = true
  try {
    const data: EmailSubscriptionCreateRequest = {
      email: emailSubscriptionForm.value.email,
      is_active: true
    }
    await createEmailSubscription(data)
    message.success('邮箱订阅已添加')
    emailSubscriptionModalVisible.value = false
    await loadEmailSubscriptions()
  } catch (error: any) {
    message.error(error.response?.data?.detail || error.message || '添加失败')
  } finally {
    savingEmailSubscription.value = false
  }
}

const toggleEmailSubscriptionStatus = async (record: EmailSubscriptionType) => {
  try {
    const data: EmailSubscriptionUpdateRequest = {
      is_active: !record.is_active
    }
    await updateEmailSubscription(record.id, data)
    message.success(record.is_active ? '已停用' : '已启用')
    await loadEmailSubscriptions()
  } catch (error: any) {
    message.error(error.response?.data?.detail || error.message || '操作失败')
  }
}

const handleDeleteEmailSubscription = (record: EmailSubscriptionType) => {
  Modal.confirm({
    title: '确认删除',
    content: `确定要删除邮箱订阅 "${record.email}" 吗？`,
    okText: '删除',
    okType: 'danger',
    cancelText: '取消',
    onOk: async () => {
      try {
        await deleteEmailSubscription(record.id)
        message.success('邮箱订阅已删除')
        await loadEmailSubscriptions()
      } catch (error: any) {
        message.error(error.response?.data?.detail || error.message || '删除失败')
      }
    },
  })
}

onMounted(() => {
  loadAIParams()
  loadPrompts()
  loadAIMethods()
  loadEmailSubscriptions()
})
</script>

<style scoped>
.settings-container {
  max-width: 1200px;
  margin: 0 auto;
  animation: fadeIn 0.5s ease;
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

h2 {
  margin: 0;
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
  padding: 32px;
}

.prompt-settings {
  margin-top: 16px;
}

.prompt-textarea {
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
  font-size: 13px;
}

:deep(.ant-form-item-label) {
  font-weight: 500;
}

:deep(.ant-descriptions) {
  margin-top: 16px;
}

.content-preview {
  color: #666;
  font-size: 12px;
}
</style>

