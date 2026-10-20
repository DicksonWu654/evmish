// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

interface ITargetFeeOracle {
    function quote(bytes calldata callData) external view returns (uint256 totalFee);
}

/// @notice GASLEFT * tx.gasprice observes only the execution transaction. It
/// does not account for a rollup's L1 data fee or a chain with different gas
/// charging rules.
contract ExecutionGasOnlyRelayer {
    function execute(address target, bytes calldata callData, uint256 gasLimit) external payable {
        uint256 beforeGas = gasleft();
        (bool ok, ) = target.call{gas: gasLimit}(callData);
        uint256 executionCost = (beforeGas - gasleft()) * tx.gasprice;
        require(ok && msg.value >= executionCost, "execution-only budget");
    }
}

/// @notice Ask the target chain's fee adapter for the total fee before sending
/// the call. The adapter can include L1 data, storage, or gas-limit charging.
contract TargetQuotedRelayer {
    ITargetFeeOracle public immutable feeOracle;

    constructor(address oracle_) {
        feeOracle = ITargetFeeOracle(oracle_);
    }

    function execute(address target, bytes calldata callData, uint256 maxFee) external payable {
        uint256 quotedFee = feeOracle.quote(callData);
        require(quotedFee <= maxFee && msg.value >= quotedFee, "target fee quote");
        (bool ok, ) = target.call(callData);
        require(ok, "target call failed");
    }
}
