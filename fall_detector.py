import openpifpaf
import torch
import argparse
import copy
import logging
import torch.multiprocessing as mp
import csv
from default_params import *
from algorithms import *
from helpers import last_ip

try:
    mp.set_start_method('spawn')
    print('spawned')
except RuntimeError:
    pass


class FallDetector:
    def __init__(self, t=DEFAULT_CONSEC_FRAMES):
        self.consecutive_frames = t
        self.args = self.cli()

    def cli(self):
        parser = argparse.ArgumentParser(
            description=__doc__,
            formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        )
        # TODO: Verify the args since they were changed in v0.10.0
        openpifpaf.decoder.cli(parser, force_complete_pose=True,
                               instance_threshold=0.2, seed_threshold=0.5)
        openpifpaf.network.nets.cli(parser)
        parser.add_argument('--resolution', default=0.4, type=float,
                            help=('Resolution prescale factor from 640x480. '
                                  'Will be rounded to multiples of 16.'))
        parser.add_argument('--resize', default=None, type=str,
                            help=('Force input image resize. '
                                  'Example WIDTHxHEIGHT.'))
        parser.add_argument('--video', default=None, type=str,
                            help='Path to the video file.')
        parser.add_argument('--video_directory',default='dataset/Activity1/Subject1/',
                            type=str,help='Diretory of video files')
        parser.add_argument('--debug', default=False, action='store_true',
                            help='debug messages and autoreload')
        parser.add_argument('--disable_cuda', default=False, action='store_true',
                            help='disables cuda support and runs from gpu')

        vis_args = parser.add_argument_group('Visualisation')
        vis_args.add_argument('--plot_graph', default=False, action='store_true',
                              help='Plot the graph of features extracted from keypoints of pose.')
        vis_args.add_argument('--joints', default=True, action='store_true',
                              help='Draw joint\'s keypoints on the output video.')
        vis_args.add_argument('--skeleton', default=True, action='store_true',
                              help='Draw skeleton on the output video.')
        vis_args.add_argument('--coco_points', default=False, action='store_true',
                              help='Visualises the COCO points of the human pose.')
        vis_args.add_argument('--save-output', default=False, action='store_true',
                              help='Save the result in a video file.')
        vis_args.add_argument('--fps', default=18, type=int,
                              help='FPS for the output video.')
        vis_args.add_argument('--out-path', default='result.avi', type=str,
                              help='Save the output video at the path specified. .avi file format.')
        vis_args.add_argument('--csv-path', default='keypoints.csv', type=str,
                              help='Save the pose coordinates into a CSV file at the path specified.')

        args = parser.parse_args()

        # Log
        logging.basicConfig(level=logging.INFO if not args.debug else logging.DEBUG)

        # Add args.device
        args.device = torch.device('cpu')
        print(args.disable_cuda)
        args.pin_memory = False
        if not args.disable_cuda and torch.cuda.is_available():
            args.device = torch.device('cuda')
            args.pin_memory = True

        if args.checkpoint is None:
            args.checkpoint = 'resnet18'

        return args

    def begin(self):
        print('begin: ', __name__)
        queue1 = mp.Queue()
        queue2 = mp.Queue()
        counter1 = mp.Value('i',0)
        counter2 = mp.Value('i',0)
        print("Queue Made")
        print(self.args)
        args1=copy.deepcopy(self.args)
        args3=copy.deepcopy(self.args)
        args1.video = self.args.video_directory+"Trial1Cam1.mp4"
        args3.video = self.args.video_directory+"Trial1Cam2.mp4"
        process1_1 = mp.Process(target=extract_keypoints,
                              args=(queue1, args1,counter1 , counter2, self.consecutive_frames))
        process1_2 = mp.Process(target=extract_keypoints,
                              args=(queue2, args3,counter2, counter1 ,self.consecutive_frames))
        process1_1.start()
        process1_2.start()
        
        print("P1 made")
        if not self.args.coco_points:
            process2_1 = mp.Process(target=alg2,
                                  args=(queue1, self.args.plot_graph, self.consecutive_frames))
            process2_2 = mp.Process(target=alg2,
                                  args=(queue2, self.args.plot_graph, self.consecutive_frames))
            print("P2 made")
            process2_1.start()
            process2_2.start()

        process1_1.join()
        process1_2.join()
        if not self.args.coco_points:
            process2_1.join()
            process2_2.join()

        return

    def get_features(self):
        queue = mp.Queue()
        feature_q = mp.Queue()
        print("Queue Made")
        process1 = mp.Process(target=extract_keypoints,
                              args=(queue, self.args, self.consecutive_frames))
        process2 = mp.Process(target=alg2,
                              args=(queue, self.args.plot_graph, self.consecutive_frames, feature_q))
        print("P1 made")
        print("P2 made")
        process1.start()
        process2.start()

        process1.join()
        process2.join()

        re_matrix = feature_q.get()[0]
        gf_matrix = feature_q.get()[0]

        _, re_last = last_ip(re_matrix)
        _, gf_last = last_ip(gf_matrix)

        re_matrix = re_matrix[:re_last]
        gf_matrix = gf_matrix[:gf_last]

        return re_matrix, gf_matrix


if __name__ == "__main__":
    f = FallDetector()
    f.begin()
    print("Done")
