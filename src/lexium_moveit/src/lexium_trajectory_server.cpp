#include <memory>
#include <thread>
#include <sstream>

#include <rclcpp/rclcpp.hpp>
#include <rclcpp_action/rclcpp_action.hpp>
#include <std_msgs/msg/float64_multi_array.hpp>
#include <control_msgs/action/follow_joint_trajectory.hpp>

class LexiumTrajectoryServer : public rclcpp::Node
{
public:
    using FollowJT =
        control_msgs::action::FollowJointTrajectory;

    using GoalHandleJT =
        rclcpp_action::ServerGoalHandle<FollowJT>;

    LexiumTrajectoryServer()
        : Node("lexium_trajectory_server")
    {
        /*
         * Publisher: sends joint targets to the Python bridge.
         *
         * Topic:   /lexium/joint_target
         * Message: Float64MultiArray — 6 joint positions in radians
         *
         * The Python bridge subscribes here and forwards
         * each point to the real arm via JAKA JSON/TLS.
         */
        joint_pub_ =
            this->create_publisher<std_msgs::msg::Float64MultiArray>(
                "/lexium/joint_target", 10);

        server_ =
            rclcpp_action::create_server<FollowJT>(
                this,
                "/arm_controller/follow_joint_trajectory",
                std::bind(&LexiumTrajectoryServer::handle_goal,
                          this,
                          std::placeholders::_1,
                          std::placeholders::_2),
                std::bind(&LexiumTrajectoryServer::handle_cancel,
                          this,
                          std::placeholders::_1),
                std::bind(&LexiumTrajectoryServer::handle_accepted,
                          this,
                          std::placeholders::_1));

        RCLCPP_INFO(get_logger(), "Lexium trajectory action server ready");
        RCLCPP_INFO(get_logger(), "Publishing joint targets to /lexium/joint_target");
    }

private:

    rclcpp_action::Server<FollowJT>::SharedPtr server_;
    rclcpp::Publisher<std_msgs::msg::Float64MultiArray>::SharedPtr joint_pub_;

    rclcpp_action::GoalResponse handle_goal(
        const rclcpp_action::GoalUUID &,
        std::shared_ptr<const FollowJT::Goal> goal)
    {
        RCLCPP_INFO(get_logger(),
                    "Received trajectory with %zu points",
                    goal->trajectory.points.size());
        return rclcpp_action::GoalResponse::ACCEPT_AND_EXECUTE;
    }

    rclcpp_action::CancelResponse handle_cancel(
        const std::shared_ptr<GoalHandleJT>)
    {
        RCLCPP_INFO(get_logger(), "Cancel request received");
        return rclcpp_action::CancelResponse::ACCEPT;
    }

    void handle_accepted(const std::shared_ptr<GoalHandleJT> goal_handle)
    {
        std::thread(std::bind(&LexiumTrajectoryServer::execute,
                              this,
                              goal_handle))
            .detach();
    }

    void execute(const std::shared_ptr<GoalHandleJT> goal_handle)
    {
        auto goal = goal_handle->get_goal();
        size_t n_points = goal->trajectory.points.size();

        RCLCPP_INFO(get_logger(), "Executing trajectory: %zu points", n_points);

        if (n_points == 0)
        {
            RCLCPP_WARN(get_logger(), "Empty trajectory — ignoring");
            auto result = std::make_shared<FollowJT::Result>();
            result->error_code =
                control_msgs::action::FollowJointTrajectory_Result::SUCCESSFUL;
            goal_handle->succeed(result);
            return;
        }

        // Publish only the final point — the goal pose.
        // MoveIt sends a dense trajectory; the JAKA arm handles
        // its own interpolation internally once given the target.
        const auto &final_point = goal->trajectory.points.back();

        if (final_point.positions.size() != 6)
        {
            RCLCPP_ERROR(get_logger(),
                         "Expected 6 joint positions, got %zu",
                         final_point.positions.size());
            auto result = std::make_shared<FollowJT::Result>();
            result->error_code =
                control_msgs::action::FollowJointTrajectory_Result::INVALID_JOINTS;
            goal_handle->abort(result);
            return;
        }

        // Log target
        std::stringstream ss;
        ss << "Target joints (rad): ";
        for (double pos : final_point.positions)
            ss << pos << "  ";
        RCLCPP_INFO(get_logger(), "%s", ss.str().c_str());

        // Publish to Python bridge
        std_msgs::msg::Float64MultiArray msg;
        msg.data = std::vector<double>(
            final_point.positions.begin(),
            final_point.positions.end());
        joint_pub_->publish(msg);

        RCLCPP_INFO(get_logger(), "Published to /lexium/joint_target");

        // Wait for arm to complete.
        // Use MoveIt's expected duration + 1s margin, clamped 2-30s.
        double expected_duration =
            final_point.time_from_start.sec +
            final_point.time_from_start.nanosec * 1e-9;
        double wait_sec = std::max(2.0, std::min(expected_duration + 1.0, 30.0));

        RCLCPP_INFO(get_logger(),
                    "Waiting %.1f s for arm to complete",
                    wait_sec);

        rclcpp::sleep_for(
            std::chrono::milliseconds(static_cast<int>(wait_sec * 1000)));

        auto result = std::make_shared<FollowJT::Result>();
        result->error_code =
            control_msgs::action::FollowJointTrajectory_Result::SUCCESSFUL;
        goal_handle->succeed(result);

        RCLCPP_INFO(get_logger(), "Trajectory execution complete");
    }
};

int main(int argc, char ** argv)
{
    rclcpp::init(argc, argv);
    auto node = std::make_shared<LexiumTrajectoryServer>();
    rclcpp::spin(node);
    rclcpp::shutdown();
    return 0;
}