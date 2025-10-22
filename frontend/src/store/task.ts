import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { TaskStatus } from '@/api/task'

export const useTaskStore = defineStore('task', () => {
  const tasks = ref<Map<number, TaskStatus>>(new Map())
  
  const allTasks = computed(() => Array.from(tasks.value.values()))
  
  const runningTasks = computed(() => 
    allTasks.value.filter(task => 
      ['pending', 'downloading', 'extracting_audio', 'transcribing', 'summarizing'].includes(task.status)
    )
  )
  
  const pendingTasks = computed(() => 
    allTasks.value.filter(task => task.status === 'pending')
  )
  
  const completedTasks = computed(() => 
    allTasks.value.filter(task => task.status === 'completed')
  )
  
  const failedTasks = computed(() => 
    allTasks.value.filter(task => task.status === 'failed')
  )
  
  const addTask = (task: TaskStatus) => {
    tasks.value.set(task.id, task)
  }
  
  const updateTask = (taskId: number, updates: Partial<TaskStatus>) => {
    const task = tasks.value.get(taskId)
    if (task) {
      tasks.value.set(taskId, { ...task, ...updates })
    }
  }
  
  const getTask = (taskId: number) => {
    return tasks.value.get(taskId)
  }
  
  const removeTask = (taskId: number) => {
    tasks.value.delete(taskId)
  }
  
  const clearTasks = () => {
    tasks.value.clear()
  }
  
  return {
    tasks,
    allTasks,
    runningTasks,
    pendingTasks,
    completedTasks,
    failedTasks,
    addTask,
    updateTask,
    getTask,
    removeTask,
    clearTasks,
  }
})
