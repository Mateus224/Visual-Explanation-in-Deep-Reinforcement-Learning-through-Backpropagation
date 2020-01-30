import argparse
import numpy as np
from environment import Environment
import matplotlib.animation as manimation
import matplotlib.pyplot as plt
from agent_dir.agent_dqn import Agent_DQN

from visualization.backpropagation import *
#import visualization.grad_cam.py


def parse():
    parser = argparse.ArgumentParser(description="DQN")
    parser.add_argument('--test_dqn', action='store_true', help='whether test DQN')
    parser.add_argument('--video_dir', default=None, help='output video directory')
    parser.add_argument('--do_render', action='store_true', help='whether render environment')
    parser.add_argument('--gbp', action='store_true', help='visualize what the network learned with Guided backpropagation')
    parser.add_argument('--gradCAM', action='store_true', help='visualize what the network learned with GradCAM')
    parser.add_argument('--gbp_GradCAM', action='store_true', help='visualize what the network learned with Guided GradCAM')
    try:
        from argument import add_arguments
        parser = add_arguments(parser)
    except:
        pass
    args = parser.parse_args()
    return args


def init_saliency_map(args, agent, history, first_frame=0, num_frames=2200, prefix='QF_', resolution=75, save_dir='./movies/', env_name='Breakout-v0'):
    visualization_network_model = build_guided_model(agent)
    visualization_network_model.load_weights(args.test_dqn_model_path)
    frame_1= np.zeros((84, 84))
    total_frames=len(history['state'])
    backprop_fn = init_guided_backprop(visualization_network_model,"dense_12")
    if args.dueling:
        backprop_fn_advatage = init_guided_backprop(visualization_network_model,"dense_10")
        fig_array = np.zeros((16,2200,84,84,3))
    else:
        fig_array = np.zeros((1,2200,84,84,3))
    print("len: ",total_frames)
    for i in range(2200):#total_frames): #num_frames
        ix = first_frame+i
        if ix < total_frames: # prevent loop from trying to process a frame ix greater than rollout length
            frame = history['state'][ix].copy()
            frame = np.expand_dims(frame, axis=0)
            if ix%100==0:
                print(ix)
            gbp_heatmap = guided_backprop(frame, backprop_fn)
            #
            history['gradients'].append(gbp_heatmap)
            if args.dueling:
                gbp_heatmap = guided_backprop(frame, backprop_fn_advatage)
                history['gradients_duel_adv'].append(gbp_heatmap)
    history_grad=history['gradients'].copy()
    for i in range(0,4):
        fig_array[i*2] = normalization(history_grad, history,i)
    if args.dueling:
        for i in range(0,4):
            history_grad_adv=history['gradients_duel_adv'].copy()
            fig_array[(i*2)+1] = normalization(history_grad_adv, history,i)
    make_movie(args,history,fig_array,first_frame,num_frames,resolution,save_dir,prefix,env_name)

def normalization(gbp_heatmap, history,i):
    gbp_heatmap=np.asarray(gbp_heatmap)
    gbp_heatmap=gbp_heatmap[:,0,:,:,:]
    #gbp_heatmap_pic=gbp_heatmap[0,:,:,:]
    gbp_heatmap-= gbp_heatmap.mean() 
    gbp_heatmap/= (gbp_heatmap.std() + 1e-5) #
    gbp_heatmap*= 0.1 
    #frame=frame[0,:,:,0]
    #print(frame)

    # clip to [0, 1]
    gbp_heatmap += 0.5
    gbp_heatmap = np.clip(gbp_heatmap, 0, 1)
    print(gbp_heatmap.shape)
    gbp_heatmap_pic1 = gbp_heatmap[:,:,:,i]
    #gbp_heatmap_pic2 = gbp_heatmap[:,:,:,1]
    frame = history['state'].copy()
    frame =np.clip(frame,0,1)
    frame = frame[:,:,:,i]
    mixed = np.stack((gbp_heatmap_pic1, frame,gbp_heatmap_pic1), axis=3) 
    return mixed

    #return mixed

def make_movie(args,history,fig_array,first_frame,num_frames,resolution,save_dir,prefix,env_name):
    movie_title ="{}-{}-{}.mp4".format(prefix, num_frames, env_name.lower())
    max_ep_len = first_frame + num_frames + 1
    FFMpegWriter = manimation.writers['ffmpeg']
    metadata = dict(title='test', artist='mateus', comment='atari-video')
    writer = FFMpegWriter(fps=8, metadata=metadata)
    total_frames = len(history['state'])
    fig = plt.figure(figsize=[6, 6*1.3], dpi=resolution)
    with writer.saving(fig, save_dir + movie_title, resolution):
        for i in range(0,2200):#total_frames): #num_frames
            plotColumns = 2
            plotRows = 4
            if args.dueling:
                titleList=["V(s; theta, beta)","A(s,a;thata,alpha)"]
                for j in range(1, plotColumns*plotRows+1):
                    img = fig_array[j-1,i,:,:,:]
                    ax=fig.add_subplot(plotRows, plotColumns, j)
                    ax.set_xlabel(titleList[(j+1)%2])
                    plt.imshow(img)
            else:
                plt.imshow(fig_array[0,i,:,:,:]) 

            writer.grab_frame() 
            fig.clear()
            if i%100==0:
                print(i)
            



def play_game(args, agent, env, total_episodes=1):
    
    history = { 'state': [], 'action': [], 'gradients':[], 'gradients_duel_adv':[],'movie_frames':[]}
    rewards = []
    for i in range(total_episodes):
        state = env.reset()
        agent.init_game_setting()
        done = False
        episode_reward = 0.0

        #playing one game
        #while(not done):
        for _ in range(2200):
            action = agent.make_action(state, test=True)
            state, reward, done, info = env.step(action)
            episode_reward += reward
            if args.gbp or args.gradCAM or args.gbp_GradCAM:
                history['state'].append(state)
                history['action'].append(action)
        rewards.append(episode_reward)
    print('Run %d episodes'%(total_episodes))
    print('Mean:', np.mean(rewards))
    init_saliency_map(args, agent, history)

    return history


def test(agent, env, total_episodes=30):
    rewards = []
    for i in range(total_episodes):
        state = env.reset()
        agent.init_game_setting()
        done = False
        episode_reward = 0.0

        #playing one game
        while(not done):
            action = agent.make_action(state, test=True)
            state, reward, done, info = env.step(action)
            episode_reward += reward

        rewards.append(episode_reward)
    print('Run %d episodes'%(total_episodes))
    print('Mean:', np.mean(rewards))


def run(args):
    if args.test_dqn:
        env = Environment('SeaquestNoFrameskip-v0', args, atari_wrapper=True, test=True)
        from agent_dir.agent_dqn import Agent_DQN
        agent = Agent_DQN(env, args)
        play_game(agent, env, total_episodes=1)






if __name__ == '__main__':
    args = parse()
    run(args)
