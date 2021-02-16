import numpy as np
import closed_loop.dynamics as dynamics
import closed_loop.analyzers as analyzers
import closed_loop.constraints as constraints
from closed_loop.utils.nn import load_controller
from closed_loop.utils.utils import init_state_range_to_polytope, get_polytope_A
import os
import argparse

def main(args):
    np.random.seed(seed=0)

    # Load NN control policy
    controller = load_controller(name=args.system)

    # Dynamics
    if args.system == 'double_integrator_mpc':
        if args.state_feedback:
            dyn = dynamics.DoubleIntegrator()
        else:
            dyn = dynamics.DoubleIntegratorOutputFeedback()
        init_state_range = np.array([ # (num_inputs, 2)
                        [2.5, 3.0], # x0min, x0max
                        [-0.25, 0.25], # x1min, x1max
        ])
    elif args.system == 'quadrotor':
        if args.state_feedback:
            dyn = dynamics.Quadrotor()
        else:
            dyn = dynamics.QuadrotorOutputFeedback()
            init_state_range = np.array([ # (num_inputs, 2)
                [4.65,4.65,2.95,0.94,-0.01,-0.01],
                [4.75,4.75,3.05,0.96,0.01,0.01]
            ]).T
    else:
        raise NotImplementedError

    partitioner_hyperparams = {
        "type": args.partitioner,
        "num_partitions": args.num_partitions,
        # "make_animation": False,
        # "show_animation": False,
    }
    propagator_hyperparams = {
        "type": args.propagator,
        "input_shape": init_state_range.shape[:-1],
    }

    # Set up analyzer (+ parititoner + propagator)
    analyzer = analyzers.ClosedLoopAnalyzer(controller, dyn)
    analyzer.partitioner = partitioner_hyperparams
    analyzer.propagator = propagator_hyperparams

    # Set up initial state set (and placeholder for reachable sets)
    if args.boundaries == "polytope":
        A_inputs, b_inputs = init_state_range_to_polytope(init_state_range)
        if system == 'quadrotor': A_out = A_inputs
        else: A_out = get_polytope_A(args.num_polytope_facets)
        input_constraint = constraints.PolytopeInputConstraint(A_inputs, b_inputs)
        output_constraint = constraints.PolytopeOutputConstraint(A_out)
    elif args.boundaries == "lp":
        input_constraint = constraints.LpInputConstraint(range=init_state_range, p=np.inf)
        output_constraint = constraints.LpOutputConstraint(p=np.inf)
    else:
        raise NotImplementedError

    # Run the analyzer N times to compute an estimated runtime
    if args.estimate_runtime:
        import time
        num_calls = 5
        times = np.empty(num_calls)
        for num in range(num_calls):
            t_start = time.time()
            output_constraint, analyzer_info = analyzer.get_reachable_set(input_constraint, output_constraint, t_max=args.t_max)
            t_end = time.time()
            t = t_end - t_start
            times[num] = t
        print("All times: {}".format(times))
        print("Avg time: {}".format(times.mean()))

    # Run analysis & generate a plot
    output_constraint, analyzer_info = analyzer.get_reachable_set(input_constraint, output_constraint, t_max=args.t_max)
    error, avg_error = analyzer.get_error(input_constraint,output_constraint, t_max=args.t_max)
    print('Final step approximation error:{:.2f}\nAverage approximation error: {:.2f}'.format(error, avg_error))

    if args.save_plot:
        save_dir = "{}/../results/closed_loop/analyzer/".format(os.path.dirname(os.path.abspath(__file__)))
        os.makedirs(save_dir, exist_ok=True)

        # Ugly logic to embed parameters in filename:
        pars = '_'.join([str(key)+"_"+str(value) for key, value in sorted(partitioner_hyperparams.items(), key=lambda kv: kv[0]) if key not in ["make_animation", "show_animation", "type"]])
        pars2 = '_'.join([str(key)+"_"+str(value) for key, value in sorted(propagator_hyperparams.items(), key=lambda kv: kv[0]) if key not in ["input_shape", "type"]])
        model_str = args.system + '_'
        analyzer_info["save_name"] = save_dir+model_str+partitioner_hyperparams['type']+"_"+propagator_hyperparams['type']+"_"+pars
        if len(pars2) > 0:
            analyzer_info["save_name"] = analyzer_info["save_name"] + "_" + pars2
        analyzer_info["save_name"] = analyzer_info["save_name"] + ".png"

    if args.show_plot or args.save_plot:
        analyzer.visualize(input_constraint, output_constraint, show_samples=True, 
            show=args.show_plot, labels=args.plot_labels, aspect=args.plot_aspect, **analyzer_info)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Analyze a closed loop system w/ NN controller.')
    parser.add_argument('--system', default='double_integrator_mpc',
                        choices=["double_integrator_mpc", "quarotor"],
                        help='which system to analyze (default: double_integrator_mpc)')
    
    parser.add_argument('--state_feedback', dest='state_feedback', action='store_true',
                        help='whether to save the visualization')
    parser.add_argument('--output_feedback', dest='state_feedback', action='store_false')
    parser.set_defaults(state_feedback=True)

    parser.add_argument('--partitioner', default='Uniform',
                        choices=["None", "Uniform"],
                        help='which partitioner to use (default: Uniform)')
    parser.add_argument('--propagator', default='IBP',
                        choices=["IBP", "CROWN", "FastLin", "SDP"],
                        help='which propagator to use (default: IBP)')
    
    parser.add_argument('--num_partitions', default=np.array([4,4]),
                        help='how many cells per dimension to use (default: [4,4])')
    parser.add_argument('--boundaries', default="lp",
                        choices=["lp", "polytope"],
                        help='what shape of convex set to bound reachable sets (default: lp)')
    parser.add_argument('--num_polytope_facets', default=8, type=int,
                        help='how many facets on constraint polytopes (default: 8)')
    parser.add_argument('--t_max', default=2., type=float,
                        help='seconds into future to compute reachable sets (default: 2.)')
    
    parser.add_argument('--estimate_runtime', dest='estimate_runtime', action='store_true')
    parser.set_defaults(estimate_runtime=False)

    parser.add_argument('--save_plot', dest='save_plot', action='store_true',
                        help='whether to save the visualization')
    parser.add_argument('--skip_save_plot', dest='feature', action='store_false')
    parser.set_defaults(save_plot=True)

    parser.add_argument('--show_plot', dest='show_plot', action='store_true',
                        help='whether to show the visualization')
    parser.add_argument('--skip_show_plot', dest='show_plot', action='store_false')
    parser.set_defaults(show_plot=False)

    parser.add_argument('--plot_labels', metavar='N', default=["x_0", "x_1"], type=str, nargs='+',
                        help='x and y labels on input partition plot (default: ["Input", None])')
    parser.add_argument('--plot_aspect', default="equal",
                        choices=["auto", "equal"],
                        help='aspect ratio on input partition plot (default: auto)')

    args = parser.parse_args()

    main(args)

    print("--- done. ---")


    