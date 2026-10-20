// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

interface ICrossDomainMessenger {
    function xDomainMessageSender() external view returns (address);
}

/// @notice An L2 contract that assumes the direct caller is the L1 owner.
/// @dev OP and Arbitrum deliver cross-domain messages through a messenger,
///      and their aliasing rules are chain-specific.
contract DirectCallerOnlyOwner {
    address public immutable owner;

    constructor(address owner_) {
        owner = owner_;
    }

    function privilegedAction() external view {
        require(msg.sender == owner, "owner only");
    }
}

/// @notice Authenticate the messenger and recover its chain-specific L1 sender.
/// @dev The messenger address and interface must be configured for the target
///      rollup. Never replace this check with tx.origin or an alias constant.
contract MessengerAuthenticatedOwner {
    address public immutable owner;
    address public immutable messenger;

    constructor(address owner_, address messenger_) {
        owner = owner_;
        messenger = messenger_;
    }

    function privilegedAction() external view {
        require(msg.sender == messenger, "messenger only");
        require(ICrossDomainMessenger(messenger).xDomainMessageSender() == owner, "L1 owner only");
    }
}
