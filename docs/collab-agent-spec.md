# Agent 协作交互规范（A2A / 控制台播报 · v2.1）

> 状态：v2.1（2026-11-02，「播报式协作」裁决落地后修订）
> 适用：所有经 agent-workbench 控制台参与 A2A 协作的 Agent
> 变更：协作群不再唤醒任何 Agent；唤醒改由执行面调度器确定性拉起（见 §2）

## 1. 事实源与通道分工

- 任务、A2A 消息、ack、状态的事实源在控制台库；一切以工具返回值为准。
- 协作群由控制台以自身应用直发**四条状态播报**（无 @、不唤醒任何人）：
  ① 〔交接〕发起方 → 收件方，附摘要与任务 id；② 〔接单〕承接方已接单；
  ③ 〔完成〕下游已完成，结论已同步；④ 〔验收〕根任务系统收口闭环。
- 群里只有这四条播报 + 人类发言。Agent 之间的一切交互走 a2a 工具与任务字段，不进群。

## 2. 唤醒机制（2026-11-02 裁决）

- Agent 被 `aw-dispatch` 调度器唤醒（每分钟确定性拉收件箱，有待处理消息才起会话），**不再被群消息唤醒**。
- 被调度器唤醒的会话是工作会话：必须完成收件箱处理链路后才允许结束，禁止直接输出 NO_REPLY（群回复纪律不适用于调度器会话）。
- 人在群里 @ 某个 Agent 仍然有效，这是人类入口；此时正常回群作答。

## 3. 承接方六步链路（收到 request / escalate 时）

1. `a2a_inbox` 拉取完整消息，记下 msg_id 与 thread_id。
2. `task_create` 新建**你自己名下**的下游任务（消息里的 task_id 是发起方的，不能用于你的 ack）。
3. `a2a_ack`：msg_id=收到的消息，task_id=第 2 步你自己的任务；控制台同事务把你的任务挂到发起方任务下（parent_task_id），并触发控制台发〔接单〕播报。
4. 按职责执行任务。
5. `a2a_send` 回执：task_id 用你自己的任务，**必须带 thread_id**（回到原线程），intent=reply，reply_to=收到的 msg_id；deadline 必填。控制台发〔完成〕播报在你 task_update 关单之后。
6. `task_update` 关单：status 按合法路径推进（见 §5），不允许跳级。

## 4. 发起方姿势

- 先 `task_create` 自己名下的任务，再 `a2a_send`（task_id=自己的任务）→ 控制台发〔交接〕播报。
- `to` 必须在自己的委派白名单内；白名单为空或不含目标时，报告人去控制台配置，不要换目标硬发。
- intent=request/escalate 必填 deadline；到期未 ack 会进死信，并向你回「消息已过期未确认,请重新发起」notify。
- **无需自己关单**：收件方回执被你 ack 即视为验收，控制台自动把根任务收口（pending→running→done 由系统代推进）并发〔验收〕播报。你的职责是及时拉收件箱、审阅回执、ack。

## 5. 状态机（控制台强校验，非法跃迁返回 VALIDATION_FAILED）

- status：pending→[running,cancelled]；running→[blocked,review,done,cancelled]；blocked→[running,cancelled]；review→[running,done,cancelled]；done / cancelled 为终态。
- stage：intake→[plan,closed]；plan→[exec,closed]；exec→[review,closed]；review→[exec,deliver]；deliver→closed；closed 为终态。
- 系统自动收口只动 status（running→done 或 pending→running→done），不改 stage；事件记 actor=system、reason=auto_close。

## 6. 常见报错语义与正确动作

| 报错 | 含义 | 正确动作 |
| --- | --- | --- |
| 下游任务不属于当前 Agent | ack 用了别人的 task_id | 用自己 `task_create` 出的任务 id 重新 ack |
| 只能以自己的任务发起 A2A | send 的 task_id 不是你的 | 换自己名下任务 |
| 目标 Agent 不在委派白名单内 | 对端白名单未配 | 报告人配控制台，不要重试或换目标 |
| reply_to 必须是同一线程内的消息 | 缺 thread_id 或跨线程引用 | 带原线程 thread_id 重发 |
| 非法状态跃迁 | 跳过了中间状态 | 按 §5 路径逐级推进 |
| 只能 ACK 发给自己的消息 | msg_id 不是发给你的 | 以 `a2a_inbox` 返回为准 |
| 消息已过期进入死信,请由发起方重新发送 | 迟到的 ack | 不再 ack；由发起方重发 |

## 7. 收件箱纪律（reply / notify）

- reply：阅读结论 → `a2a_ack` 确认（这就是验收动作，会触发根任务收口）→ 无需回执。
- notify（含死信回执「请重新发起」）：阅读 → `a2a_ack` 清空收件箱；发起方收到「请重新发起」时重新 `a2a_send`（uuid 幂等，不会重复投递）。
- 收件箱不积压：调度器每次唤醒都会拉取，未 ack 的消息会反复可见，直到确认。

## 8. 禁止事项

- 禁止把工作过程、结论、任务详情发进协作群。
- 禁止用别人的任务 id ack、跨线程回执、跳级关单。
- 禁止在调度器唤醒的会话里不处理收件箱直接结束。
